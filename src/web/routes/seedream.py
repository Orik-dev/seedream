from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional, Tuple, List

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, update

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage

from bot.routers.generation import send_generation_result
from bot.states import CreateStates, GenStates
from core.config import settings
from db.engine import SessionLocal
from db.models import Task, User
from services.telegram_safe import safe_send_text

router = APIRouter()
log = logging.getLogger("seedream")

_TERMINAL_SUCCESS = {"success"}
_TERMINAL_FAILED = {"fail", "failed", "error"}

def _normalize_status(s: str) -> str:
    s = (s or "").lower().strip()
    if s in _TERMINAL_SUCCESS:
        return "completed"
    if s in _TERMINAL_FAILED:
        return "failed"
    return "failed"

async def _acquire_webhook_lock(task_id: str, ttl: int = 180) -> Optional[Tuple[aioredis.Redis, str]]:
    r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB_CACHE)
    key = f"wb:lock:{task_id}"
    try:
        ok = await r.set(key, "1", nx=True, ex=ttl)
        if ok:
            return r, key
        return None
    except Exception:
        try:
            await r.aclose()
        except Exception:
            pass
        return None

async def _release_webhook_lock(lock: Optional[Tuple[aioredis.Redis, str]]) -> None:
    if not lock:
        return
    r, key = lock
    try:
        await r.delete(key)
    except Exception:
        pass
    finally:
        try:
            await r.aclose()
        except Exception:
            pass

async def _clear_pending_marker(task_id: str) -> None:
    try:
        r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB_CACHE)
        await r.delete(f"task:pending:{task_id}")
        await r.aclose()
    except Exception:
        pass

async def _clear_wait_and_reset(bot, chat_id: int, *, back_to: str = "auto") -> None:
    """Снимает 'Генерирую…' и возвращает пользователя"""
    r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB_FSM)
    storage = RedisStorage(redis=r, key_builder=DefaultKeyBuilder(with_bot_id=True))
    me = await bot.get_me()
    fsm = FSMContext(storage=storage, key=StorageKey(me.id, chat_id, chat_id))

    data = await fsm.get_data()
    wait_id = data.get("wait_msg_id")
    if wait_id:
        try:
            await bot.delete_message(chat_id, wait_id)
        except Exception:
            pass
        await fsm.update_data(wait_msg_id=None)

    mode = (data.get("mode") or "").lower()
    target = back_to
    if target == "auto":
        target = "create" if mode == "create" else "edit"

    if target == "create":
        await fsm.update_data(mode="create", edits=[], photos=[])
        await fsm.set_state(CreateStates.waiting_prompt)
    else:
        await fsm.set_state(GenStates.waiting_prompt)

@router.post("/webhook/seedream")
async def seedream_callback(req: Request):
    """✅ Вебхук с защитой от двойного списания"""
    token = req.query_params.get("t")
    if token != settings.WEBHOOK_SECRET_TOKEN:
        raise HTTPException(403, "forbidden")

    try:
        payload = await req.json()
    except Exception:
        log.warning(json.dumps({"event": "webhook.hit", "error": "invalid_json"}, ensure_ascii=False))
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    log.info(json.dumps({
        "event": "webhook.hit",
        "keys": list(payload.keys()),
        "raw_len": len(json.dumps(payload, ensure_ascii=False)),
    }, ensure_ascii=False))

    data = payload.get("data", {})
    task_id = data.get("taskId")
    raw_state = str(data.get("state", "")).lower()
    state = _normalize_status(raw_state)
    
    result_json_str = data.get("resultJson", "{}")
    try:
        result_json = json.loads(result_json_str)
    except Exception:
        result_json = {}
    
    result_urls = result_json.get("resultUrls", [])
    seed = result_json.get("seed")
    if seed:
        try:
            seed = int(seed)
        except (ValueError, TypeError):
            seed = None
    
    fail_code = data.get("failCode")
    fail_msg = data.get("failMsg")

    if not task_id:
        return JSONResponse({"ok": False, "error": "no_task_id"}, status_code=400)
    
    await _clear_pending_marker(task_id)

    lock = await _acquire_webhook_lock(task_id, ttl=180)
    if lock is None:
        log.info(json.dumps({"event": "webhook.skip_locked", "task_id": task_id}, ensure_ascii=False))
        return JSONResponse({"ok": True})

    try:
        async with SessionLocal() as s:
            task = (await s.execute(select(Task).where(Task.task_uuid == task_id))).scalar_one_or_none()
            if not task:
                log.info(json.dumps({"event": "webhook.no_task", "task_id": task_id}, ensure_ascii=False))
                return JSONResponse({"ok": True})

            if getattr(task, "delivered", False):
                log.info(json.dumps({"event": "webhook.already_delivered", "task_id": task_id}, ensure_ascii=False))
                return JSONResponse({"ok": True})

            await s.execute(
                update(Task)
                .where(Task.id == task.id)
                .values(status=state, credits_used=len(result_urls) if result_urls else 1, seed=str(seed) if seed else None)
            )
            await s.commit()

            user = await s.get(User, task.user_id)
            bot = req.app.state.bot

            # ---- SUCCESS ----
            if state == "completed":
                if not result_urls:
                    await _clear_wait_and_reset(bot, user.chat_id, back_to="auto")
                    await safe_send_text(bot, user.chat_id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")
                    await s.execute(update(Task).where(Task.id == task.id).values(delivered=True))
                    await s.commit()
                    log.info(json.dumps({"event": "webhook.completed.no_urls", "task_id": task_id}, ensure_ascii=False))
                    return JSONResponse({"ok": True})

                # 🆕 ИДЕМПОТЕНТНОСТЬ - проверка ПЕРЕД списанием
                idempotency_key = f"credits:debited:{task_id}"
                r_cache = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB_CACHE)
                
                try:
                    already_debited = await r_cache.exists(idempotency_key)
                    if already_debited:
                        log.warning(json.dumps({
                            "event": "webhook.already_debited",
                            "task_id": task_id
                        }, ensure_ascii=False))
                    else:
                        # СПИСЫВАЕМ только если ещё НЕ списано
                        num_images = len(result_urls)
                        before = int(user.balance_credits or 0)
                        new_balance = max(0, before - num_images)
                        await s.execute(
                            update(User).where(User.id == user.id).values(balance_credits=new_balance)
                        )
                        await s.commit()

                        log.info(json.dumps({
                            "event": "credits_deducted",
                            "task_id": task_id,
                            "user_id": user.id,
                            "images": num_images,
                            "before": before,
                            "after": new_balance
                        }, ensure_ascii=False))

                        # Ставим маркер "списано"
                        await r_cache.setex(idempotency_key, 86400, "1")
                finally:
                    await r_cache.aclose()

                # Скачивание файлов
                out_dir = "/tmp/seedream"
                os.makedirs(out_dir, exist_ok=True)
                
                local_paths: List[str] = []
                download_errors = 0
                
                async with httpx.AsyncClient() as client:
                    for idx, image_url in enumerate(result_urls):
                        local_path = os.path.join(out_dir, f"{task_id}_{idx}.png")
                        
                        try:
                            head_resp = await client.head(image_url, timeout=10)
                            content_length = int(head_resp.headers.get("content-length", 0))
                            
                            if content_length > 20 * 1024 * 1024:
                                log.warning(json.dumps({
                                    "event": "webhook.image_too_large",
                                    "task_id": task_id,
                                    "image_idx": idx,
                                    "size_mb": content_length / 1024 / 1024
                                }, ensure_ascii=False))
                                download_errors += 1
                                continue
                        except Exception:
                            pass
                        
                        last_exc = None
                        for attempt in range(3):
                            try:
                                r = await client.get(image_url, timeout=120)
                                r.raise_for_status()
                                
                                content = r.content
                                if len(content) > 20 * 1024 * 1024:
                                    log.warning(json.dumps({
                                        "event": "webhook.downloaded_too_large",
                                        "task_id": task_id,
                                        "image_idx": idx,
                                        "size_mb": len(content) / 1024 / 1024
                                    }, ensure_ascii=False))
                                    download_errors += 1
                                    break
                                
                                with open(local_path, "wb") as f:
                                    f.write(content)
                                local_paths.append(local_path)
                                last_exc = None
                                break
                            except Exception as e:
                                last_exc = e
                                await asyncio.sleep(2)
                        
                        if last_exc:
                            download_errors += 1
                            log.warning(json.dumps({
                                "event": "webhook.download_failed",
                                "task_id": task_id,
                                "image_idx": idx,
                                "error": str(last_exc)
                            }, ensure_ascii=False))

                if download_errors == len(result_urls):
                    await _clear_wait_and_reset(bot, user.chat_id, back_to="auto")
                    await safe_send_text(bot, user.chat_id, "⚠️ Ошибка загрузки результатов.\nНапишите в поддержку: @guard_gpt")
                    await s.execute(update(Task).where(Task.id == task.id).values(delivered=True))
                    await s.commit()
                    return JSONResponse({"ok": True})

                await send_generation_result(
                    user.chat_id, 
                    task_id, 
                    task.prompt, 
                    result_urls,
                    local_paths,
                    seed,
                    bot
                )
                
                await s.execute(update(Task).where(Task.id == task.id).values(delivered=True))
                await s.commit()
                
                log.info(json.dumps({
                    "event": "webhook.completed.sent",
                    "task_id": task_id,
                    "images": len(result_urls),
                    "seed": seed
                }, ensure_ascii=False))
                
                return JSONResponse({"ok": True})

            # ---- FAILED ----
            await _clear_wait_and_reset(bot, user.chat_id, back_to="auto")
            error_msg = "⚠️ Не удалось сгенерировать изображение."
            if fail_msg:
                error_msg += f"\n\nПричина: {fail_msg[:200]}"
            error_msg += "\n\nИзмените промт и попробуйте снова."
            
            await safe_send_text(bot, user.chat_id, error_msg)
            await s.execute(update(Task).where(Task.id == task.id).values(delivered=True))
            await s.commit()
            
            log.info(json.dumps({
                "event": "webhook.failed", 
                "task_id": task_id, 
                "raw_state": raw_state,
                "fail_code": fail_code,
                "fail_msg": fail_msg
            }, ensure_ascii=False))
            
            return JSONResponse({"ok": True})

    finally:
        await _release_webhook_lock(lock)