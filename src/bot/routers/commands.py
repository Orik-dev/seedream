# from __future__ import annotations

# import os

# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import (
#     Message,
#     CallbackQuery,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     FSInputFile,
# )
# from aiogram.fsm.context import FSMContext
# from sqlalchemy import select

# from bot.states import CreateStates
# from bot.keyboards import kb_topup_methods, kb_aspect_ratio_selector, validate_aspect_ratio
# from services.users import ensure_user
# from services.telegram_safe import safe_answer, safe_send_text, safe_edit_text
# from core.config import settings
# from db.engine import SessionLocal
# from db.models import User
# from services.queue import enqueue_generation

# router = Router()

# def get_asset_path(filename: str) -> str:
#     base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
#     return os.path.join(base_dir, "assets", filename)

# # ======================= /start =======================

# @router.message(Command("start"))
# async def cmd_start(m: Message, state: FSMContext):
#     await state.clear()
#     await ensure_user(m.from_user)
#     img_path = get_asset_path("seedream.jpg")

#     caption = (
#         "🌟 <b>Добро пожаловать в Seedream V4</b> — мощная генерация изображений:\n\n"
#         "🎁 У вас есть <b>5 бесплатных генераций</b>\n\n"
#         "💰 Тариф: <b>1 генерация</b> = <b>1 изображение</b>\n\n"
#         # "Рекомендуем изучить инструкцию!\n"
#         # "📖 <a href=\"https://t.me/seedream_examples\">Инструкция и примеры</a>\n\n"
#         "⚙️ Настройки: /set\n\n"
#         "Используйте команды из меню или нажмите кнопку ниже 👇\n\n"
#         "Пользуясь ботом, Вы принимаете наше "
#         "<a href=\"https://docs.google.com/document/d/139A-rEgNeA6CrcOaOsOergVVx4bUq8NFlTLx4eD4MfE/edit?usp=drivesdk\">пользовательское соглашение</a> "
#         "и <a href=\"https://telegram.org/privacy-tpa\">политику конфиденциальности</a>."
#     )

#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[[InlineKeyboardButton(text="✨ Создать изображение", callback_data="start_create")]]
#     )

#     if os.path.exists(img_path):
#         await m.answer_photo(
#             photo=FSInputFile(img_path),
#             caption=caption,
#             reply_markup=keyboard,
#             parse_mode="HTML",
#         )
#     else:
#         await safe_send_text(m.bot, m.chat.id, caption, reply_markup=keyboard)

# # ======================= /help =======================

# @router.message(Command("help"))
# async def cmd_help(m: Message, state: FSMContext):
#     await state.clear()
#     text = (
#         "❓ <b>Помощь</b>\n\n"
#         "Вот что я умею:\n\n"
#         "🚀 <b>/start</b> — запуск и краткое введение\n"
#         "📸 <b>/edit</b> — загрузите фото + запрос → редактирование изображения\n"
#         "✨ <b>/create</b> — создание изображения по текстовому описанию\n"
#         # "⚙️ <b>/set</b> — настройки качества и количества изображений\n"
#         "💳 <b>/buy</b> — баланс и пополнение (₽/⭐)\n"
#         "🎥 <b>/example</b> — посмотреть примеры работ\n"
#         "🤖 <b>/bots</b> — другие наши проекты\n"
#         "❓ <b>/help</b> — эта справка\n\n"
#         "✉️ Вопросы? Напишите: @guard_gpt"
#     )
#     await safe_send_text(m.bot, m.chat.id, text)

# # ======================= /buy =======================

# @router.message(Command("buy"))
# async def cmd_buy(m: Message, state: FSMContext):
#     try:
#         user = await ensure_user(m.from_user)
#         await state.clear()
#         await safe_send_text(
#             m.bot,
#             m.chat.id,
#             (
#                 f"Ваш баланс: <b>{user.balance_credits}</b> генераций.\n"
#                 f"Тариф: 1 генерация — 1 изображение.\n\n"
#                 "Выберите способ оплаты:"
#             ),
#             reply_markup=kb_topup_methods(),
#         )
#     except Exception:
#         await safe_send_text(m.bot, m.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

# # ======================= /example =======================

# @router.message(Command("example"))
# async def cmd_example(m: Message, state: FSMContext):
#     await state.clear()
#     caption = (
#         "📌 <b>Примеры работ Seedream</b>\n\n"
#         "Хотите увидеть, как выглядит результат генерации? "
#         "Нажмите кнопку ниже и перейдите в наш канал 👇"
#     )
#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="📂 Примеры", url="https://t.me/seedream_examples")]
#         ]
#     )
#     await safe_send_text(m.bot, m.chat.id, caption, reply_markup=keyboard)

# # ======================= /bots =======================

# @router.message(Command("bots"))
# async def show_other_bots(m: Message, state: FSMContext):
#     await state.clear()
#     text = (
#         "🔗 <b>Ознакомьтесь с нашими другими полезными ботами:</b>\n\n"
#         "🍌 <b>Nano Banana</b> — AI фотошоп от Google Gemini\n"
#         "👉 <a href='https://t.me/nano_banana_bot'>@nano_banana_bot</a>\n\n"
#         "🎥 <b>Sora 2 · Создать видео</b> — создавайте супер реалистичные, захватывающие 10 секундные видео с озвучкой в нейросети от создателей ChatGPT.\n"
#         "👉 <a href='https://t.me/sora_ai_ibot'>@sora_ai_ibot</a>\n\n"
#         "🤖 <b>DeepSeek</b> — лучшая китайская нейросеть. Официальный API. Голосовое общение.\n"
#         "👉 <a href='https://t.me/DeepSeek_telegram_bot'>@DeepSeek_telegram_bot</a>\n\n"
#         "🍔 <b>КБЖУ по фото</b> — считает калории по фото или голосовому.\n"
#         "👉 <a href='https://t.me/calories_by_photo_bot'>@calories_by_photo_bot</a>\n\n"
#         "🎥 <b>Google Veo AI</b> — генерация видео с помощью ИИ от Google.\n"
#         "👉 <a href='https://t.me/veo_google_ai_bot'>@veo_google_ai_bot</a>\n\n"
#         "🖼 <b>Реалистичное оживление фото</b> — оживляет статичные фотографии, превращая их в видео.\n"
#         "👉 <a href='https://t.me/Ozhivlenie_foto_bot'>@Ozhivlenie_foto_bot</a>\n\n"
#         "📩 <b>Скачивание из Instagram/YouTube/TikTok</b> — скачивайте видео бесплатно.\n"
#         "👉 <a href='https://t.me/save_video_aibot'>@save_video_aibot</a>"
#     )
#     await safe_send_text(m.bot, m.chat.id, text, disable_web_page_preview=True)

# # ======================= /live =======================

# @router.message(Command("live"))
# async def cmd_live(m: Message, state: FSMContext):
#     await state.clear()
#     text = (
#         "<b>Рекомендуем эти боты для оживления фото</b>\n\n"
#         "🖼 <b>Реалистичное оживление фото</b>\n"
#         "Реалистично оживляет фотографии, превращая их в видео.\n"
#         "👉 <a href='https://t.me/Ozhivlenie_foto_bot'>@Ozhivlenie_foto_bot</a>\n\n"
#         "🎥 <b>Sora 2 · Создать видео</b> — создавайте супер реалистичные, захватывающие 10 секундные видео с озвучкой в нейросети от создателей ChatGPT.\n"
#         "👉 <a href='https://t.me/sora_ai_ibot'>@sora_ai_ibot</a>\n\n"
#         "🎥 <b>Google Veo 3</b> — генерация видео от Google. Может оживить со звуком. 8 секунд.\n"
#         "👉 <a href='https://t.me/veo_google_ai_bot'>@veo_google_ai_bot</a>\n\n"
#     )
#     await safe_send_text(m.bot, m.chat.id, text, disable_web_page_preview=True)

# # ======================= Callback для кнопки "Создать" =======================

# @router.callback_query(F.data == "start_create")
# async def callback_start_create(c: CallbackQuery, state: FSMContext):
#     """✅ Кнопка 'Создать изображение' из /start - полный сброс состояния"""
#     await safe_answer(c)
#     await state.clear()
    
#     async with SessionLocal() as s:
#         user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one_or_none()
#         if not user:
#             await safe_send_text(c.bot, c.message.chat.id, "Нажмите /start")
#             return
        
#         required_credits = user.max_images
#         if user.balance_credits < required_credits:
#             await safe_send_text(
#                 c.bot, c.message.chat.id,
#                 f"Недостаточно генераций.\n\nТребуется: {required_credits}\nВаш баланс: {user.balance_credits}\n\nПополните: /buy"
#             )
#             return
    
#     await state.set_state(CreateStates.selecting_aspect_ratio)
#     await state.update_data(mode="create", photos=[], edits=[])
    
#     await safe_send_text(
#         c.bot, c.message.chat.id,
#         "Выберите соотношение сторон для изображения:",
#         reply_markup=kb_aspect_ratio_selector()
#     )

# # ======================= /create =======================

# @router.message(Command("create"))
# async def cmd_create(m: Message, state: FSMContext):
#     """✅ Полный сброс состояния перед /create"""
#     await state.clear()
    
#     async with SessionLocal() as s:
#         user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one_or_none()
#         if not user:
#             await safe_send_text(m.bot, m.chat.id, "Нажмите /start")
#             return
        
#         required_credits = user.max_images
#         if user.balance_credits < required_credits:
#             await safe_send_text(
#                 m.bot, m.chat.id,
#                 f"Недостаточно генераций.\n\nТребуется: {required_credits}\nВаш баланс: {user.balance_credits}\n\nПополните: /buy"
#             )
#             return
    
#     await state.set_state(CreateStates.selecting_aspect_ratio)
#     await state.update_data(mode="create", photos=[], edits=[])
#     await safe_send_text(
#         m.bot, m.chat.id,
#         "Выберите соотношение сторон для изображения:",
#         reply_markup=kb_aspect_ratio_selector()
#     )

# @router.callback_query(CreateStates.selecting_aspect_ratio, F.data.startswith("ar_"))
# async def handle_create_aspect_ratio(c: CallbackQuery, state: FSMContext):
#     """✅ Выбор соотношения сторон для /create"""
#     await safe_answer(c)
#     ar = c.data.replace("ar_", "")
    
#     if ar == "skip":
#         ar = None
#     elif not validate_aspect_ratio(ar):
#         return
    
#     async with SessionLocal() as s:
#         user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
#         image_resolution = user.image_resolution
#         max_images = user.max_images
    
#     await state.update_data(
#         aspect_ratio=ar, 
#         image_resolution=image_resolution,
#         max_images=max_images
#     )
#     await state.set_state(CreateStates.waiting_prompt)
    
#     await safe_edit_text(
#         c.message, 
#         # f"✅ Выбрано: {ar or 'авто'}\n\n"
#         # f"📊 Настройки:\n"
#         # f"├ Качество: <b>{image_resolution}</b>\n"
#         # f"└ Количество: <b>{max_images}</b> изображений\n\n"
#         f"💡 Введите промт для генерации"
#     )

# @router.message(CreateStates.waiting_prompt, F.text, lambda m: not m.text.startswith("/"))
# async def create_got_prompt(m: Message, state: FSMContext) -> None:
#     """Получили промт для создания изображения"""
#     prompt = (m.text or "").strip()

#     if len(prompt) < 3:
#         await safe_send_text(m.bot, m.chat.id, "Промт слишком короткий. Минимум 3 символа 🙂")
#         return
#     if len(prompt) > 2000:
#         prompt = prompt[:2000]
        
#     data = await state.get_data()
#     aspect_ratio = data.get("aspect_ratio")
#     image_resolution = data.get("image_resolution", "1K")
#     max_images = data.get("max_images", 1)

#     await state.set_state(CreateStates.generating)
#     wait_msg = await safe_send_text(m.bot, m.chat.id, f"Генерирую...")
#     await state.update_data(
#         mode="create", 
#         prompt=prompt,
#         wait_msg_id=getattr(wait_msg, "message_id", None),
#     )
    
#     await enqueue_generation(
#         m.from_user.id, 
#         prompt, 
#         [], 
#         aspect_ratio=aspect_ratio, 
#         image_resolution=image_resolution,
#         max_images=max_images,
#         seed=None
#     )

# # ======================= Итеративное редактирование Create =======================



# @router.callback_query(CreateStates.final_menu, F.data == "new_image")
# async def create_new_image(c: CallbackQuery, state: FSMContext) -> None:
#     """✅ Полный сброс состояния"""
#     await safe_answer(c)
#     await state.clear()
#     await cmd_create(c.message, state)

# @router.callback_query(CreateStates.final_menu, F.data == "regenerate")
# async def create_regenerate(c: CallbackQuery, state: FSMContext) -> None:
#     """Сгенерировать похожее с seed"""
#     await safe_answer(c)
#     data = await state.get_data()
#     last_result_urls = data.get("last_result_urls", [])
#     prompt = data.get("prompt")
#     aspect_ratio = data.get("aspect_ratio")
#     image_resolution = data.get("image_resolution", "1K")
#     max_images = data.get("max_images", 1)
#     seed = data.get("last_seed")
    
#     if not prompt:
#         await safe_send_text(c.bot, c.message.chat.id, "⚠️ Ошибка. Напишите @guard_gpt")
#         return
    
#     try:
#         await safe_send_text(c.bot, c.message.chat.id, f"Генерирую...")
        
#         await enqueue_generation(
#             c.from_user.id, 
#             prompt, 
#             last_result_urls if last_result_urls else [],
#             aspect_ratio=aspect_ratio,
#             image_resolution=image_resolution,
#             max_images=max_images,
#             seed=seed
#         )
#     except Exception:
#         await safe_send_text(c.bot, c.message.chat.id, "⚠️ Ошибка. Напишите @guard_gpt")
        
# # ======================= CREATE FINAL MENU =======================

# @router.callback_query(CreateStates.final_menu, F.data == "new_image")
# async def create_new_image(c: CallbackQuery, state: FSMContext):
#     """Начать заново в режиме create"""
#     await safe_answer(c)
#     await state.clear()
#     await cmd_create(c.message, state)

# # @router.callback_query(CreateStates.final_menu, F.data == "regenerate")
# # async def create_regenerate(c: CallbackQuery, state: FSMContext):
# #     """Сгенерировать похожее в режиме create"""
# #     await safe_answer(c)
    
# #     data = await state.get_data()
# #     prompt = data.get("prompt")
# #     seed = data.get("last_seed")
# #     aspect_ratio = data.get("aspect_ratio", "9:16")
    
# #     if not prompt:
# #         await safe_send_text(c.bot, c.message.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")
# #         return
    
# #     async with SessionLocal() as s:
# #         user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
# #         image_resolution = user.image_resolution
# #         max_images = user.max_images
    
# #     try:
# #         await safe_send_text(c.bot, c.message.chat.id, "Генерирую…")
# #         await enqueue_generation(
# #             c.from_user.id, 
# #             prompt, 
# #             [],
# #             aspect_ratio=aspect_ratio,
# #             image_resolution=image_resolution,
# #             max_images=max_images,
# #             seed=seed
# #         )
# #     except Exception:
# #         await safe_send_text(c.bot, c.message.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

# @router.message(CreateStates.final_menu, F.text.startswith("/"))
# async def create_final_menu_commands(m: Message, state: FSMContext):
#     """Команды в final_menu режима create"""
#     cmd = (m.text or "").split(maxsplit=1)[0].lower()

#     if cmd in ["/start", "/help", "/buy", "/balance"]:
#         return
    
#     if cmd in ["/edit", "/gen", "/create"]:
#         await safe_send_text(
#             m.bot, m.chat.id,
#             "💡 Вы уже в режиме создания.\n\n"
#             "Просто напишите новый промт, или нажмите кнопку внизу."
#         )
#         return

# @router.message(CreateStates.final_menu, F.text)
# async def create_final_menu_new_prompt(m: Message, state: FSMContext):
#     """Новый промт в режиме create"""
#     prompt = (m.text or "").strip()
    
#     if len(prompt) < 3:
#         await safe_send_text(m.bot, m.chat.id, "Промт слишком короткий. Минимум 3 символа 🙂")
#         return
#     if len(prompt) > 2000:
#         prompt = prompt[:2000]
    
#     data = await state.get_data()
#     aspect_ratio = data.get("aspect_ratio", "9:16")
    
#     async with SessionLocal() as s:
#         user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one()
#         image_resolution = user.image_resolution
#         max_images = user.max_images
    
#     await state.set_state(CreateStates.generating)
#     wait_msg = await safe_send_text(m.bot, m.chat.id, "Генерирую…")
#     await state.update_data(
#         mode="create",
#         prompt=prompt,
#         wait_msg_id=getattr(wait_msg, "message_id", None),
#         image_resolution=image_resolution,
#         max_images=max_images,
#         aspect_ratio=aspect_ratio,
#     )
    
#     await enqueue_generation(
#         m.from_user.id, 
#         prompt, 
#         [],
#         aspect_ratio=aspect_ratio,
#         image_resolution=image_resolution,
#         max_images=max_images
#     )

from __future__ import annotations

import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from bot.states import CreateStates
from bot.keyboards import kb_topup_methods, kb_aspect_ratio_selector, validate_aspect_ratio
from services.users import ensure_user
from services.telegram_safe import safe_answer, safe_send_text, safe_edit_text
from core.config import settings
from db.engine import SessionLocal
from db.models import User
from services.queue import enqueue_generation

router = Router()

def get_asset_path(filename: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_dir, "assets", filename)

# ======================= /start =======================

@router.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await ensure_user(m.from_user)
    img_path = get_asset_path("seedream.jpg")

    caption = (
        "🌟 <b>Добро пожаловать в Seedream V4</b> — мощная генерация изображений:\n\n"
        "🎁 У вас есть <b>5 бесплатных генераций</b>\n\n"
        "💰 Тариф: <b>1 генерация</b> = <b>1 изображение</b>\n\n"
        "Используйте команды из меню или нажмите кнопку ниже 👇\n\n"
        "Пользуясь ботом, Вы принимаете наше "
        "<a href=\"https://docs.google.com/document/d/139A-rEgNeA6CrcOaOsOergVVx4bUq8NFlTLx4eD4MfE/edit?usp=drivesdk\">пользовательское соглашение</a> "
        "и <a href=\"https://telegram.org/privacy-tpa\">политику конфиденциальности</a>."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✨ Создать изображение", callback_data="start_create")]]
    )

    if os.path.exists(img_path):
        await m.answer_photo(
            photo=FSInputFile(img_path),
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        await safe_send_text(m.bot, m.chat.id, caption, reply_markup=keyboard)

# ======================= /help =======================

@router.message(Command("help"))
async def cmd_help(m: Message, state: FSMContext):
    await state.clear()
    text = (
        "❓ <b>Помощь</b>\n\n"
        "Вот что я умею:\n\n"
        "🚀 <b>/start</b> — запуск и краткое введение\n"
        "📸 <b>/edit</b> — загрузите фото + запрос → редактирование изображения\n"
        "✨ <b>/create</b> — создание изображения по текстовому описанию\n"
        "💳 <b>/buy</b> — баланс и пополнение (₽/⭐)\n"
        "🎥 <b>/example</b> — посмотреть примеры работ\n"
        "🤖 <b>/bots</b> — другие наши проекты\n"
        "❓ <b>/help</b> — эта справка\n\n"
        "✉️ Вопросы? Напишите: @guard_gpt"
    )
    await safe_send_text(m.bot, m.chat.id, text)

# ======================= /buy =======================

@router.message(Command("buy"))
async def cmd_buy(m: Message, state: FSMContext):
    try:
        user = await ensure_user(m.from_user)
        await state.clear()
        await safe_send_text(
            m.bot,
            m.chat.id,
            (
                f"Ваш баланс: <b>{user.balance_credits}</b> генераций.\n"
                f"Тариф: 1 генерация — 1 изображение.\n\n"
                "Выберите способ оплаты:"
            ),
            reply_markup=kb_topup_methods(),
        )
    except Exception:
        await safe_send_text(m.bot, m.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

# ======================= /example =======================

@router.message(Command("example"))
async def cmd_example(m: Message, state: FSMContext):
    await state.clear()
    caption = (
        "📌 <b>Примеры работ Seedream</b>\n\n"
        "Хотите увидеть, как выглядит результат генерации? "
        "Нажмите кнопку ниже и перейдите в наш канал 👇"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📂 Примеры", url="https://t.me/seedream_examples")]
        ]
    )
    await safe_send_text(m.bot, m.chat.id, caption, reply_markup=keyboard)

# ======================= /bots =======================

@router.message(Command("bots"))
async def show_other_bots(m: Message, state: FSMContext):
    await state.clear()
    text = (
        "🔗 <b>Ознакомьтесь с нашими другими полезными ботами:</b>\n\n"
        "🍌 <b>Nano Banana</b> — AI фотошоп от Google Gemini\n"
        "👉 <a href='https://t.me/nano_banana_bot'>@nano_banana_bot</a>\n\n"
        "🎥 <b>Sora 2 · Создать видео</b> — создавайте супер реалистичные, захватывающие 10 секундные видео с озвучкой в нейросети от создателей ChatGPT.\n"
        "👉 <a href='https://t.me/sora_ai_ibot'>@sora_ai_ibot</a>\n\n"
        "🤖 <b>DeepSeek</b> — лучшая китайская нейросеть. Официальный API. Голосовое общение.\n"
        "👉 <a href='https://t.me/DeepSeek_telegram_bot'>@DeepSeek_telegram_bot</a>\n\n"
        "🍔 <b>КБЖУ по фото</b> — считает калории по фото или голосовому.\n"
        "👉 <a href='https://t.me/calories_by_photo_bot'>@calories_by_photo_bot</a>\n\n"
        "🎥 <b>Google Veo AI</b> — генерация видео с помощью ИИ от Google.\n"
        "👉 <a href='https://t.me/veo_google_ai_bot'>@veo_google_ai_bot</a>\n\n"
        "🖼 <b>Реалистичное оживление фото</b> — оживляет статичные фотографии, превращая их в видео.\n"
        "👉 <a href='https://t.me/Ozhivlenie_foto_bot'>@Ozhivlenie_foto_bot</a>\n\n"
        "📩 <b>Скачивание из Instagram/YouTube/TikTok</b> — скачивайте видео бесплатно.\n"
        "👉 <a href='https://t.me/save_video_aibot'>@save_video_aibot</a>"
    )
    await safe_send_text(m.bot, m.chat.id, text, disable_web_page_preview=True)

# ======================= /live =======================

@router.message(Command("live"))
async def cmd_live(m: Message, state: FSMContext):
    await state.clear()
    text = (
        "<b>Рекомендуем эти боты для оживления фото</b>\n\n"
        "🖼 <b>Реалистичное оживление фото</b>\n"
        "Реалистично оживляет фотографии, превращая их в видео.\n"
        "👉 <a href='https://t.me/Ozhivlenie_foto_bot'>@Ozhivlenie_foto_bot</a>\n\n"
        "🎥 <b>Sora 2 · Создать видео</b> — создавайте супер реалистичные, захватывающие 10 секундные видео с озвучкой в нейросети от создателей ChatGPT.\n"
        "👉 <a href='https://t.me/sora_ai_ibot'>@sora_ai_ibot</a>\n\n"
        "🎥 <b>Google Veo 3</b> — генерация видео от Google. Может оживить со звуком. 8 секунд.\n"
        "👉 <a href='https://t.me/veo_google_ai_bot'>@veo_google_ai_bot</a>\n\n"
    )
    await safe_send_text(m.bot, m.chat.id, text, disable_web_page_preview=True)

# ======================= Callback для кнопки "Создать" =======================

@router.callback_query(F.data == "start_create")
async def callback_start_create(c: CallbackQuery, state: FSMContext):
    """✅ Кнопка 'Создать изображение' из /start"""
    await safe_answer(c)
    await state.clear()
    
    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one_or_none()
        if not user:
            await safe_send_text(c.bot, c.message.chat.id, "Нажмите /start")
            return
        
        required_credits = user.max_images
        if user.balance_credits < required_credits:
            await safe_send_text(
                c.bot, c.message.chat.id,
                f"Недостаточно генераций.\n\nТребуется: {required_credits}\nВаш баланс: {user.balance_credits}\n\nПополните: /buy"
            )
            return
    
    await state.set_state(CreateStates.selecting_aspect_ratio)
    await state.update_data(mode="create", photos=[], edits=[])
    
    await safe_send_text(
        c.bot, c.message.chat.id,
        "Выберите соотношение сторон для изображения:",
        reply_markup=kb_aspect_ratio_selector()
    )

# ======================= /create =======================

@router.message(Command("create"))
async def cmd_create(m: Message, state: FSMContext):
    """✅ Полный сброс состояния перед /create"""
    await state.clear()
    
    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one_or_none()
        if not user:
            await safe_send_text(m.bot, m.chat.id, "Нажмите /start")
            return
        
        required_credits = user.max_images
        if user.balance_credits < required_credits:
            await safe_send_text(
                m.bot, m.chat.id,
                f"Недостаточно генераций.\n\nТребуется: {required_credits}\nВаш баланс: {user.balance_credits}\n\nПополните: /buy"
            )
            return
    
    await state.set_state(CreateStates.selecting_aspect_ratio)
    await state.update_data(mode="create", photos=[], edits=[])
    await safe_send_text(
        m.bot, m.chat.id,
        "Выберите соотношение сторон для изображения:",
        reply_markup=kb_aspect_ratio_selector()
    )

@router.callback_query(CreateStates.selecting_aspect_ratio, F.data.startswith("ar_"))
async def handle_create_aspect_ratio(c: CallbackQuery, state: FSMContext):
    """✅ Выбор соотношения сторон для /create"""
    await safe_answer(c)
    ar = c.data.replace("ar_", "")
    
    if ar == "skip":
        ar = None
    elif not validate_aspect_ratio(ar):
        return
    
    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
        image_resolution = user.image_resolution
        max_images = user.max_images
    
    await state.update_data(
        aspect_ratio=ar, 
        image_resolution=image_resolution,
        max_images=max_images
    )
    await state.set_state(CreateStates.waiting_prompt)
    
    await safe_edit_text(
        c.message, 
        f"💡 Введите промт для генерации"
    )

@router.message(CreateStates.waiting_prompt, F.text, lambda m: not m.text.startswith("/"))
async def create_got_prompt(m: Message, state: FSMContext) -> None:
    """Получили промт для создания изображения"""
    prompt = (m.text or "").strip()

    if len(prompt) < 3:
        await safe_send_text(m.bot, m.chat.id, "Промт слишком короткий. Минимум 3 символа 🙂")
        return
    if len(prompt) > 2000:
        prompt = prompt[:2000]
        
    data = await state.get_data()
    aspect_ratio = data.get("aspect_ratio")
    image_resolution = data.get("image_resolution", "4K")
    max_images = data.get("max_images", 1)

    await state.set_state(CreateStates.generating)
    wait_msg = await safe_send_text(m.bot, m.chat.id, f"Генерирую...")
    await state.update_data(
        mode="create", 
        prompt=prompt,
        wait_msg_id=getattr(wait_msg, "message_id", None),
    )
    
    await enqueue_generation(
        m.from_user.id, 
        prompt, 
        [], 
        aspect_ratio=aspect_ratio, 
        image_resolution=image_resolution,
        max_images=max_images,
        seed=None
    )

# ======================= CREATE FINAL MENU =======================

@router.callback_query(CreateStates.final_menu, F.data == "new_image")
async def create_new_image(c: CallbackQuery, state: FSMContext):
    """✅ Начать заново в режиме create"""
    await safe_answer(c)
    await state.clear()
    await cmd_create(c.message, state)

@router.callback_query(CreateStates.final_menu, F.data == "regenerate")
async def create_regenerate(c: CallbackQuery, state: FSMContext):
    """✅ Сгенерировать похожее в режиме create"""
    await safe_answer(c)
    
    data = await state.get_data()
    prompt = data.get("prompt")
    seed = data.get("last_seed")
    aspect_ratio = data.get("aspect_ratio", "9:16")
    
    if not prompt:
        await safe_send_text(c.bot, c.message.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")
        return
    
    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
        image_resolution = user.image_resolution
        max_images = user.max_images
    
    try:
        await safe_send_text(c.bot, c.message.chat.id, "Генерирую…")
        await enqueue_generation(
            c.from_user.id, 
            prompt, 
            [],
            aspect_ratio=aspect_ratio,
            image_resolution=image_resolution,
            max_images=max_images,
            seed=seed
        )
    except Exception:
        await safe_send_text(c.bot, c.message.chat.id, "⚠️ Произошла ошибка.\nНапишите в поддержку: @guard_gpt")

@router.message(CreateStates.final_menu, F.text.startswith("/"))
async def create_final_menu_commands(m: Message, state: FSMContext):
    """Команды в final_menu режима create"""
    cmd = (m.text or "").split(maxsplit=1)[0].lower()

    if cmd in ["/start", "/help", "/buy", "/balance"]:
        return
    
    if cmd in ["/edit", "/gen", "/create"]:
        await safe_send_text(
            m.bot, m.chat.id,
            "💡 Вы уже в режиме создания.\n\n"
            "Просто напишите новый промт, или нажмите кнопку внизу."
        )
        return

@router.message(CreateStates.final_menu, F.text)
async def create_final_menu_new_prompt(m: Message, state: FSMContext):
    """Новый промт в режиме create"""
    prompt = (m.text or "").strip()
    
    if len(prompt) < 3:
        await safe_send_text(m.bot, m.chat.id, "Промт слишком короткий. Минимум 3 символа 🙂")
        return
    if len(prompt) > 2000:
        prompt = prompt[:2000]
    
    data = await state.get_data()
    aspect_ratio = data.get("aspect_ratio", "9:16")
    
    async with SessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one()
        image_resolution = user.image_resolution
        max_images = user.max_images
    
    await state.set_state(CreateStates.generating)
    wait_msg = await safe_send_text(m.bot, m.chat.id, "Генерирую…")
    await state.update_data(
        mode="create",
        prompt=prompt,
        wait_msg_id=getattr(wait_msg, "message_id", None),
        image_resolution=image_resolution,
        max_images=max_images,
        aspect_ratio=aspect_ratio,
    )
    
    await enqueue_generation(
        m.from_user.id, 
        prompt, 
        [],
        aspect_ratio=aspect_ratio,
        image_resolution=image_resolution,
        max_images=max_images
    )