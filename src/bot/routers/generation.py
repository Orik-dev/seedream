from __future__ import annotations

import os
import sys
import asyncio
import logging
from typing import List, Dict, Optional

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.states import CreateStates
from db.engine import SessionLocal
from db.models import User
from services.pricing import CREDITS_PER_GENERATION
from bot.states import GenStates
from bot.keyboards import kb_gen_step_back, kb_final_result
from services.queue import enqueue_generation
from services.telegram_safe import (
    safe_answer,
    safe_send_text,
    safe_send_photo,
    safe_send_document,
    safe_edit_text,
    safe_delete_message,
)
from core.config import settings

log = logging.getLogger("generation")
router = Router()

_DEBOUNCE_TASKS: Dict[int, asyncio.Task] = {}

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

PLACEHOLDER_PATH = resource_path(os.path.join('..', '..', 'assets', 'placeholder_light_gray_block.png'))

@router.message(F.photo | F.document)
async def auto_start_on_photo(m: Message, state: FSMContext):
    """✅ Автоматический старт /edit при получении фото"""
    caption = (m.caption or "").strip().lower()
    if caption.startswith("/broadcast"):
        return
    
    is_image = False
    if m.photo:
        is_image = True
    elif m.document and _is_image_document(m):
        is_image = True
    
    if not is_image:
        return
    
    cur = await state.get_state()
    
    if cur in {
        CreateStates.selecting_aspect_ratio.state,
        CreateStates.waiting_prompt.state,
        CreateStates.generating.state,
        CreateStates.final_menu.state,
    }:
        return
    
    if cur is None or cur == GenStates.final_menu.state:
        await cmd_gen(m, state, show_intro=False)
        if m.photo:
            await handle_images(m, state)
        elif _is_image_document(m):
            await handle_document_images(m, state)
        return
    
    if cur == GenStates.uploading_images.state:
        if caption and not caption.startswith("/"):
            await state.update_data(auto_prompt=caption)
        
        if m.photo:
            await handle_images(m, state)
        elif _is_image_document(m):
            await handle_document_images(m, state)

async def _kick_generation_now(m: Message, state: FSMContext, prompt: str) -> None:
    """Запускает генерацию сразу"""
    prompt = (prompt or "").strip()
    if len(prompt) < 3:
        await state.set_state(GenStates.waiting_prompt)
        await safe_send_text(m.bot, m.chat.id, "Введите промт (что изменить):", reply_markup=kb_gen_step_back())
        return

    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await state.set_state(GenStates.waiting_prompt)
        await safe_send_text(m.bot, m.chat.id, "Введите промт (что изменить):", reply_markup=kb_gen_step_back())
        return

    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one()
        image_resolution = user.image_resolution
        max_images = user.max_images

    vertical = data.get("vertical_orientation", True)
    aspect_ratio = "9:16" if vertical else "16:9"  # ← Определяем AR

    file_ids = [p["file_id"] for p in photos]
    await state.set_state(GenStates.generating)
    wait_msg = await safe_send_text(m.bot, m.chat.id, f"Генерирую...")
    await state.update_data(
        prompt=prompt,
        base_prompt=prompt,
        edits=[],
        mode="edit",
        wait_msg_id=getattr(wait_msg, "message_id", None),
        image_resolution=image_resolution,
        max_images=max_images,
        aspect_ratio=aspect_ratio,  # ← Добавляем
    )

    await enqueue_generation(
        m.from_user.id, 
        prompt, 
        file_ids,
        image_resolution=image_resolution,
        max_images=max_images,
        aspect_ratio=aspect_ratio  # ← Передаем
    )

@router.callback_query(GenStates.waiting_prompt, F.data.startswith("toggle_orientation_"))
async def toggle_orientation(c: CallbackQuery, state: FSMContext) -> None:
    """Переключение вертикально/горизонтально"""
    await safe_answer(c)
    
    current = c.data.split("_")[-1] == "True"
    new_vertical = not current
    
    await state.update_data(vertical_orientation=new_vertical)
    
    checkbox = "✅" if new_vertical else "☑️"
    text = f"{checkbox} Вертикально" if new_vertical else f"{checkbox} Горизонтально"
    
    new_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=f"toggle_orientation_{new_vertical}")]
        ]
    )
    
    try:
        await c.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception:
        pass
    
@router.message(Command("edit"))
@router.message(Command("gen"))
async def cmd_gen(m: Message, state: FSMContext, user_id: Optional[int] = None, show_intro: bool = True):
    """✅ Полностью сбрасываем состояние перед началом /edit"""
    await state.clear()
    uid = user_id or m.from_user.id

    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.chat_id == uid))).scalar_one_or_none()
        if u is None:
            await safe_send_text(m.bot, m.chat.id, "Нажмите /start, чтобы инициализироваться.")
            return

        required_credits = u.max_images * CREDITS_PER_GENERATION
        if u.balance_credits < required_credits:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Карта РФ(₽)", callback_data="m_rub")],
                [InlineKeyboardButton(text="⭐️ Звёзды", callback_data="m_stars")],
            ])
            await safe_send_text(
                m.bot, m.chat.id,
                f"Недостаточно генераций.\n\nТребуется: {required_credits}\nВаш баланс: {u.balance_credits}\n\nПополните баланс:",
                reply_markup=keyboard,
            )
            return

    await start_generation(m, state, show_intro=show_intro)

@router.callback_query(F.data == "run_gen")
async def callback_run_gen(c: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Создать'"""
    await safe_answer(c)
    await state.clear()
    await state.set_state(CreateStates.selecting_aspect_ratio)
    await state.update_data(mode="create", photos=[], edits=[])
    
    from bot.keyboards import kb_aspect_ratio_selector
    await safe_send_text(
        c.bot, c.message.chat.id,
        "Выберите соотношение сторон для изображения:",
        reply_markup=kb_aspect_ratio_selector()
    )

async def start_generation(m: Message, state: FSMContext, show_intro: bool = True) -> None:
    _cancel_debounce(m.chat.id)
    await state.clear()
    await state.set_state(GenStates.uploading_images)
    await state.update_data(photos=[], album_id=None, finalized=False)

    if show_intro:
        text = "Пришлите 1-6 фотографий которые нужно изменить или объединить"
        if os.path.exists(PLACEHOLDER_PATH):
            await safe_send_photo(m.bot, m.chat.id, FSInputFile(PLACEHOLDER_PATH), caption=text)
        else:
            await safe_send_text(m.bot, m.chat.id, text)

def _is_image_document(msg: Message) -> bool:
    if not msg.document:
        return False
    mt = (msg.document.mime_type or "").lower()
    if mt.startswith("image/"):
        return True
    name = (msg.document.file_name or "").lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if name.endswith(ext):
            return True
    return False

def _cancel_debounce(chat_id: int) -> None:
    task = _DEBOUNCE_TASKS.pop(chat_id, None)
    if task and not task.done():
        task.cancel()

async def _finalize_to_prompt(m: Message, state: FSMContext) -> None:
    """Финализация загрузки фото и переход к вводу промта"""
    _cancel_debounce(m.chat.id)

    data = await state.get_data()
    if data.get("finalized"):
        return

    photos: List[Dict[str, str]] = data.get("photos", [])
    if not photos:
        return

    await state.update_data(finalized=True, vertical_orientation=True)  # ← По умолчанию вертикально

    auto_prompt = (data.get("auto_prompt") or "").strip()
    if auto_prompt:
        await state.update_data(auto_prompt=None)
        return await _kick_generation_now(m, state, auto_prompt)

    await state.set_state(GenStates.waiting_prompt)
    await safe_send_text(m.bot, m.chat.id, "Введите промт (что изменить):", reply_markup=kb_gen_step_back(vertical=True))

def _schedule_album_finalize(m: Message, state: FSMContext, delay: float = 2.0):
    """Планирование финализации после загрузки альбома"""
    async def _debounce():
        try:
            await asyncio.sleep(delay)
            await _finalize_to_prompt(m, state)
        except asyncio.CancelledError:
            return

    _cancel_debounce(m.chat.id)
    _DEBOUNCE_TASKS[m.chat.id] = asyncio.create_task(_debounce())

async def _accept_photo(m: Message, state: FSMContext, item: Dict[str, str]) -> None:
    data = await state.get_data()
    photos: List[Dict[str, str]] = data.get("photos", [])
    album_id: Optional[str] = data.get("album_id")
    finalized: bool = data.get("finalized", False)

    if finalized:
        await safe_send_text(m.bot, m.chat.id, "Изображения уже приняты. Чтобы заменить — нажмите «↩️ Назад».")
        return

    if len(photos) >= 6:
        _cancel_debounce(m.chat.id)
        await safe_send_text(m.bot, m.chat.id, "⚠️ Можно загрузить не более 6 изображений.")
        return

    mgid = getattr(m, "media_group_id", None)

    if not photos:
        if mgid:
            await state.update_data(album_id=str(mgid))
            photos.append(item)
            await state.update_data(photos=photos)
            _schedule_album_finalize(m, state, delay=2.0)
            return
        else:
            photos.append(item)
            await state.update_data(photos=photos)
            await _finalize_to_prompt(m, state)
            return

    if album_id is not None:
        if mgid and str(mgid) == album_id:
            photos.append(item)
            await state.update_data(photos=photos)
            _schedule_album_finalize(m, state, delay=2.0)
            return
        else:
            await safe_send_text(m.bot, m.chat.id, "Изображения уже приняты. Чтобы заменить — нажмите «↩️ Назад».")
            return

    await safe_send_text(m.bot, m.chat.id, "Изображения уже приняты. Чтобы заменить — нажмите «↩️ Назад».")
    return

@router.message(GenStates.uploading_images, F.photo)
async def handle_images(m: Message, state: FSMContext) -> None:
    try:
        if (m.caption or "").strip():
            await state.update_data(auto_prompt=(m.caption or "").strip())
        await _accept_photo(m, state, {"type": "photo", "file_id": m.photo[-1].file_id})
    except Exception:
        await safe_send_text(m.bot, m.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

@router.message(GenStates.uploading_images, F.document)
async def handle_document_images(m: Message, state: FSMContext) -> None:
    try:
        if not _is_image_document(m):
            await safe_send_text(m.bot, m.chat.id, "Можно прикрепить только изображения. Поддержка: PNG, JPG, WEBP.")
            return
        if (m.caption or "").strip():
            await state.update_data(auto_prompt=(m.caption or "").strip())
        await _accept_photo(m, state, {"type": "document", "file_id": m.document.file_id})
    except Exception:
        await safe_send_text(m.bot, m.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

@router.message(GenStates.uploading_images)
async def handle_text_while_upload(m: Message, state: FSMContext) -> None:
    await safe_send_text(m.bot, m.chat.id, "Пришлите 1-6 фотографий которые нужно изменить или объединить")

@router.callback_query(GenStates.waiting_prompt, F.data == "back_to_images")
async def back_to_images(c: CallbackQuery, state: FSMContext) -> None:
    await safe_answer(c)
    _cancel_debounce(c.message.chat.id)
    await state.set_state(GenStates.uploading_images)
    await state.update_data(photos=[], album_id=None, finalized=False)
    await safe_edit_text(c.message, "Пришлите 1-6 фотографий которые нужно изменить или объединить")

@router.message(GenStates.waiting_prompt, F.text, lambda m: not m.text.startswith("/"))
async def got_user_prompt(m: Message, state: FSMContext) -> None:
    prompt = m.text.strip()
    if not prompt:
        await safe_send_text(m.bot, m.chat.id, "Введите промт (что изменить):")
        return
    if len(prompt) < 3:
        await safe_send_text(m.bot, m.chat.id, "Промт слишком короткий. Опишите задачу минимум в 3 символах 🙂")
        return
    if len(prompt) > 2000:
        prompt = prompt[:2000]

    data = await state.get_data()
    photos: List[Dict[str, str]] = data.get("photos", [])
    file_ids = [p["file_id"] for p in photos]
    
    vertical = data.get("vertical_orientation", True)
    aspect_ratio = "9:16" if vertical else "16:9"  # ← Определяем AR

    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one()
        image_resolution = user.image_resolution
        max_images = user.max_images

    await state.set_state(GenStates.generating)
    try:
        wait_msg = await safe_send_text(m.bot, m.chat.id, f"Генерирую...")
        await state.update_data(
            prompt=prompt,
            base_prompt=prompt,
            edits=[],
            mode="edit",
            wait_msg_id=getattr(wait_msg, "message_id", None),
            image_resolution=image_resolution,
            max_images=max_images,
            aspect_ratio=aspect_ratio,  # ← Добавляем
        )

        await enqueue_generation(
            m.from_user.id, 
            prompt, 
            file_ids,
            image_resolution=image_resolution,
            max_images=max_images,
            aspect_ratio=aspect_ratio  # ← Передаем
        )
    except Exception:
        await safe_send_text(m.bot, m.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

@router.message(GenStates.final_menu, F.text, lambda m: not m.text.startswith("/"))
async def handle_final_menu_message(m: Message, state: FSMContext) -> None:
    """✅ Правки после результата в /gen"""
    if not m.text:
        await safe_send_text(m.bot, m.chat.id, "Напишите текстом, что изменить в результате, и я сгенерирую новую версию.")
        return

    new_change = (m.text or "").strip()
    data = await state.get_data()
    photos: List[Dict[str, str]] = data.get("photos") or []
    
    if not photos:
        await safe_send_text(m.bot, m.chat.id, "Не удалось найти исходные изображения. Нажмите «Начать заново».")
        return

    base_prompt = (data.get("base_prompt") or data.get("prompt") or "").strip()
    edits = list(data.get("edits") or [])
    if new_change:
        edits.append(new_change)

    cumulative_prompt = " ".join([base_prompt] + edits).strip()
    if len(cumulative_prompt) < 3:
        await safe_send_text(m.bot, m.chat.id, "Опишите правку чуть подробнее (минимум 3 символа).")
        return
    if len(cumulative_prompt) > 4000:
        cumulative_prompt = cumulative_prompt[:4000]

    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one()
        image_resolution = user.image_resolution
        max_images = user.max_images
    
    seed = data.get("last_seed")
    aspect_ratio = data.get("aspect_ratio")  # ← Сохраняем AR

    await state.set_state(GenStates.generating)
    try:
        wait_msg = await safe_send_text(m.bot, m.chat.id, f"Генерирую...")
        await state.update_data(
            prompt=cumulative_prompt,
            edits=edits,
            mode="edit",
            wait_msg_id=getattr(wait_msg, "message_id", None),
            image_resolution=image_resolution,
            max_images=max_images,
        )
        
        file_ids = [p["file_id"] for p in photos]
        await enqueue_generation(
            m.from_user.id, 
            cumulative_prompt, 
            file_ids,
            image_resolution=image_resolution,
            max_images=max_images,
            seed=seed,
            aspect_ratio=aspect_ratio  # ← Передаем
        )
    except Exception:
        await safe_send_text(m.bot, m.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

@router.callback_query(F.data == "new_image")
async def new_image_any_state(c: CallbackQuery, state: FSMContext) -> None:
    """✅ Полный сброс состояния"""
    await safe_answer(c)
    _cancel_debounce(c.message.chat.id)
    await state.clear()
    await start_generation(c.message, state, show_intro=True)

@router.callback_query(GenStates.final_menu, F.data == "regenerate")
async def regenerate(c: CallbackQuery, state: FSMContext) -> None:
    """✅ Сгенерировать похожее - используем seed"""
    await safe_answer(c)
    data = await state.get_data()
    prompt = data.get("prompt")
    photos: List[Dict[str, str]] = data.get("photos")
    seed = data.get("last_seed")
    
    if not (prompt and photos):
        await safe_send_text(c.bot, c.message.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")
        return
    
    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
        image_resolution = user.image_resolution
        max_images = user.max_images
    
    try:
        await safe_send_text(c.bot, c.message.chat.id, f"Генерирую...")
        file_ids = [p["file_id"] for p in photos]
        await enqueue_generation(
            c.from_user.id, 
            prompt, 
            file_ids,
            image_resolution=image_resolution,
            max_images=max_images,
            seed=seed
        )
    except Exception:
        await safe_send_text(c.bot, c.message.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

@router.callback_query(GenStates.final_menu, F.data == "send_file")
async def send_file_cb(c: CallbackQuery, state: FSMContext) -> None:
    await safe_answer(c)
    data = await state.get_data()
    file_paths = data.get("file_paths", [])
    if file_paths:
        for fp in file_paths:
            if os.path.exists(fp):
                await safe_send_document(c.bot, c.message.chat.id, fp, caption="Файл в максимальном качестве")
    else:
        await safe_send_text(c.bot, c.message.chat.id, "Файлы недоступны. Попробуйте сгенерировать снова.")

@router.callback_query(GenStates.final_menu, F.data == "cancel")
async def cancel_session(c: CallbackQuery, state: FSMContext) -> None:
    await safe_answer(c)
    _cancel_debounce(c.message.chat.id)
    await state.clear()
    await safe_send_text(c.bot, c.message.chat.id, "Сессия завершена. Наберите /gen для нового изображения.")
    try:
        await safe_delete_message(c.bot, c.message.chat.id, c.message.message_id)
    except Exception:
        pass

async def send_generation_result(
    chat_id: int,
    task_uuid: str,
    prompt: str,
    image_urls: List[str],
    file_paths: List[str],
    seed: Optional[int],
    bot: Bot,
) -> None:
    """✅ Отправка результатов генерации"""
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
    from aiogram.fsm.storage.base import StorageKey
    import redis.asyncio as redis

    redis_cli = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB_FSM)
    storage = RedisStorage(redis=redis_cli, key_builder=DefaultKeyBuilder(with_bot_id=True))
    bot_info = await bot.get_me()
    state = FSMContext(storage=storage, key=StorageKey(bot_info.id, chat_id, chat_id))

    data = await state.get_data()
    wait_msg_id = data.get("wait_msg_id")
    if wait_msg_id:
        try:
            await bot.delete_message(chat_id, wait_msg_id)
        except Exception:
            pass
        await state.update_data(wait_msg_id=None)

    mode = (data.get("mode") or "edit").lower().strip()

    for idx, (img_url, fp) in enumerate(zip(image_urls, file_paths)):
        caption = None
        reply_markup = None
        
        if idx == len(image_urls) - 1:
            caption = "<b>Если хотите что-то изменить или добавить напишите в чат ⬇️</b>"
            reply_markup = kb_final_result()
        
        await safe_send_photo(bot, chat_id, img_url, caption=caption, reply_markup=reply_markup)
    
    for fp in file_paths:
        if os.path.exists(fp):
            await safe_send_document(bot, chat_id, fp, caption="Скачать в максимальном качестве")
    
    if mode == "create_edit":
        mode = "create"

    if mode == "create":
        await state.update_data(
            mode="create",
            prompt=prompt,
            last_result_urls=image_urls,
            file_paths=file_paths,
            wait_msg_id=None,
            last_seed=seed,
        )
        await state.set_state(CreateStates.final_menu)
        return

    photos = data.get("photos", [])
    base_prompt = data.get("base_prompt") or prompt
    edits = data.get("edits") or []
    await state.update_data(
        mode="edit",
        prompt=prompt,
        base_prompt=base_prompt,
        edits=edits,
        photos=photos,
        file_paths=file_paths,
        last_seed=seed,
    )
    await state.set_state(GenStates.final_menu)