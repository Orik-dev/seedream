from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
import redis.asyncio as aioredis
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from uuid import uuid4

from core.config import settings
from db.engine import SessionLocal
from db.models import Task, User
from services.pricing import CREDITS_PER_GENERATION
from vendors.seedream import SeedreamClient, SeedreamError
from services.broadcast import broadcast_send

log = logging.getLogger("worker")

def _j(event: str, **fields) -> str:
    return json.dumps({"event": event, **fields}, ensure_ascii=False)

async def _tg_file_to_url(bot: Bot, file_id: str, *, cid: str) -> str:
    """Возвращает публичный URL файла Telegram"""
    f = await bot.get_file(file_id)
    file_path = f.file_path
    file_size = getattr(f, "file_size", None) or 0

    if file_size > 10 * 1024 * 1024:
        log.error(_j("queue.image_too_large", cid=cid, size=file_size))
        raise ValueError("image too large")

    lower = (file_path or "").lower()
    if not any(lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
        log.error(_j("queue.image_unsupported_ext", cid=cid, file_path=file_path))
        raise ValueError("unsupported image ext")

    return f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"

async def enqueue_generation(
    chat_id: int, 
    prompt: str, 
    photos: List[str], 
    aspect_ratio: Optional[str] = None,
    image_resolution: str = "1K",
    max_images: int = 1,
    seed: Optional[int] = None
) -> None:
    """Ставит в очередь генерацию изображения"""
    log.info(_j("enqueue_generation", chat_id=chat_id, prompt_len=len(prompt), 
               photos_count=len(photos), resolution=image_resolution, max_images=max_images))
    
    redis_pool = await create_pool(
        RedisSettings(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            database=settings.REDIS_DB_CACHE,
        )
    )
    
    job = await redis_pool.enqueue_job(
        "process_generation", 
        chat_id, 
        prompt, 
        photos, 
        aspect_ratio,
        image_resolution,
        max_images,
        seed
    )
    
    log.info(_j("enqueue_generation.success", chat_id=chat_id, job_id=str(job.job_id) if job else None))

async def startup(ctx: dict[str, Bot]):
    log.info("worker_startup_begin")
    ctx["bot"] = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    log.info("worker_startup_complete")

async def shutdown(ctx: dict[str, Bot]):
    log.info("worker_shutdown_begin")
    bot: Bot = ctx.get("bot")
    if bot:
        await bot.session.close()
    log.info("worker_shutdown_complete")

async def _clear_waiting_message(bot: Bot, chat_id: int) -> None:
    try:
        r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB_FSM)
        storage = RedisStorage(redis=r, key_builder=DefaultKeyBuilder(with_bot_id=True))
        me = await bot.get_me()
        fsm = FSMContext(storage=storage, key=StorageKey(me.id, chat_id, chat_id))
        data = await fsm.get_data()
        msg_id = data.get("wait_msg_id")
        if msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
            await fsm.update_data(wait_msg_id=None)
    except Exception:
        pass

async def _maybe_refund_if_deducted(chat_id: int, task_uuid: str, amount: int, cid: str, reason: str) -> None:
    """Возврат кредитов если они были списаны"""
    rcache = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB_CACHE)
    deb_key = f"credits:debited:{task_uuid}"
    try:
        debited = await rcache.get(deb_key)
    except Exception:
        debited = None
    if not debited:
        log.info(_j("refund.skipped_not_debited", cid=cid, chat_id=chat_id, task_uuid=task_uuid))
        return

    try:
        async with SessionLocal() as s:
            q = await s.execute(select(User).where(User.chat_id == chat_id))
            u = q.scalar_one_or_none()
            if u is not None:
                await s.execute(
                    update(User)
                    .where(User.id == u.id)
                    .values(balance_credits=User.balance_credits + amount)
                )
                await s.commit()
                log.info(_j("refund.ok", cid=cid, chat_id=chat_id, task_uuid=task_uuid, amount=amount, reason=reason))
                try:
                    await rcache.delete(deb_key)
                except Exception:
                    pass
    except Exception:
        log.exception(_j("refund.db_error", cid=cid, task_uuid=task_uuid))

async def process_generation(
    ctx: dict[str, Bot], 
    chat_id: int, 
    prompt: str, 
    photos: List[str], 
    aspect_ratio: Optional[str] = None,
    image_resolution: str = "1K",
    max_images: int = 1,
    seed: Optional[int] = None
) -> Dict[str, Any] | None:
    bot: Bot = ctx["bot"]
    api = SeedreamClient()  # 🆕 Будем закрывать в finally
    cid = uuid4().hex[:12]

    log.info(_j("queue.process.start", cid=cid, chat_id=chat_id, photos_in=len(photos or []),
               prompt_len=len(prompt or ""), resolution=image_resolution, max_images=max_images, seed=seed))

    try:
        async with SessionLocal() as s:
            try:
                q = await s.execute(select(User).where(User.chat_id == chat_id))
                user = q.scalar_one_or_none()
                if user is None:
                    log.warning(_j("queue.user_not_found", cid=cid, chat_id=chat_id))
                    await _clear_waiting_message(bot, chat_id)
                    try:
                        await bot.send_message(chat_id, "Нажмите /start для инициализации")
                    except Exception:
                        pass
                    return {"ok": False, "error": "user_not_found"}
            except OperationalError:
                log.error(_j("queue.db_unavailable", cid=cid))
                await _clear_waiting_message(bot, chat_id)
                try:
                    await bot.send_message(chat_id, "⚠️ Ошибка БД. Напишите @guard_gpt")
                except Exception:
                    pass
                return {"ok": False, "error": "db_unavailable"}

            required_credits = max_images * CREDITS_PER_GENERATION
            if user.balance_credits < required_credits:
                log.info(_j("queue.balance.insufficient", cid=cid, required=required_credits, balance=user.balance_credits))
                await bot.send_message(
                    chat_id, 
                    f"Недостаточно генераций.\nТребуется: {required_credits}\nВаш баланс: {user.balance_credits}\n\nПополните: /buy"
                )
                return {"ok": False, "error": "insufficient_credits"}

            callback = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/webhook/seedream?t={settings.WEBHOOK_SECRET_TOKEN}"
            
            if photos:
                image_urls: List[str] = []
                for item in photos[:10]:
                    try:
                        if isinstance(item, str) and item.startswith("http"):
                            image_urls.append(item)
                        else:
                            image_urls.append(await _tg_file_to_url(bot, item, cid=cid))
                    except Exception:
                        log.exception(_j("queue.fetch_image_url.failed", cid=cid, file_id=item))
                
                if not image_urls:
                    await bot.send_message(chat_id, "Ошибка обработки изображений. Попробуйте снова")
                    return {"ok": False, "error": "images_prepare_failed"}
                
                log.info(_j("queue.images.prepared", cid=cid, count=len(image_urls)))
                
                try:
                    task_id = await api.create_task_edit(
                        prompt,
                        image_urls=image_urls,
                        callback_url=callback,
                        image_resolution=image_resolution,
                        aspect_ratio=aspect_ratio,
                        max_images=max_images,
                        seed=seed,
                        cid=cid,
                    )
                    log.info(_j("queue.create_task_edit.ok", cid=cid, task_id=task_id))
                except Exception as e:
                    log.error(_j("queue.seedream_error", cid=cid, error=str(e)))
                    await _clear_waiting_message(bot, chat_id)
                    try:
                        await bot.send_message(chat_id, "⚠️ Ошибка генерации. Напишите @guard_gpt")
                    except Exception:
                        pass
                    return {"ok": False, "error": "seedream_error"}
            else:
                try:
                    task_id = await api.create_task_text_to_image(
                        prompt,
                        callback_url=callback,
                        aspect_ratio=aspect_ratio,
                        image_resolution=image_resolution,
                        max_images=max_images,
                        seed=seed,
                        cid=cid,
                    )
                    log.info(_j("queue.create_task_t2i.ok", cid=cid, task_id=task_id))
                except Exception as e:
                    log.error(_j("queue.seedream_error", cid=cid, error=str(e)))
                    await _clear_waiting_message(bot, chat_id)
                    try:
                        await bot.send_message(chat_id, "⚠️ Ошибка генерации. Напишите @guard_gpt")
                    except Exception:
                        pass
                    return {"ok": False, "error": "seedream_error"}

            log.info(_j("queue.create_task.ok", cid=cid, task_id=task_id))

            try:
                task = Task(user_id=user.id, prompt=prompt, task_uuid=task_id, status="queued", delivered=False)
                s.add(task)
                await s.commit()
                log.info(_j("queue.db_task_saved", cid=cid, task_id=task_id))
            except Exception:
                log.warning(_j("queue.db_write_failed", cid=cid, task_id=task_id))

        return {"ok": True, "task_id": task_id}

    except Exception:
        log.exception(_j("queue.fatal", cid=cid))
        await _clear_waiting_message(bot, chat_id)
        if 'task_id' in locals():
            await _maybe_refund_if_deducted(chat_id, task_id, max_images, cid, reason="internal")
        try:
            await bot.send_message(chat_id, "⚠️ Ошибка. Напишите @guard_gpt")
        except Exception:
            pass
        return {"ok": False, "error": "internal"}
    
    finally:
        # 🆕 ВСЕГДА закрываем HTTP клиент SeedreamClient
        try:
            await api.aclose()
            log.info(_j("queue.api_client_closed", cid=cid))
        except Exception as e:
            log.warning(_j("queue.api_client_close_failed", cid=cid, error=str(e)))

class WorkerSettings:
    functions = [process_generation, broadcast_send]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, database=settings.REDIS_DB_CACHE
    )
    job_timeout = 259200
    keep_result = 0

log.info("worker_settings_initialized")
