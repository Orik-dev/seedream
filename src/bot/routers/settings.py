# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
# from sqlalchemy import select, update

# from db.engine import SessionLocal
# from db.models import User
# from services.telegram_safe import safe_answer, safe_edit_text, safe_send_text

# router = Router()

# def kb_settings_menu() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="🎨 Качество изображения", callback_data="set_quality")],
#         [InlineKeyboardButton(text="🖼 Количество изображений", callback_data="set_max_images")],
#         [InlineKeyboardButton(text="↩️ Закрыть", callback_data="close_settings")],
#     ])

# def kb_quality_settings(current: str) -> InlineKeyboardMarkup:
#     buttons = []
#     for q in ["1K", "2K", "4K"]:
#         mark = "✅ " if q == current else "⚪️ "
#         buttons.append([InlineKeyboardButton(text=f"{mark}{q}", callback_data=f"setq_{q}")])
#     buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_settings")])
#     return InlineKeyboardMarkup(inline_keyboard=buttons)

# def kb_max_images_settings(current: int) -> InlineKeyboardMarkup:
#     buttons = []
#     for n in range(1, 7):
#         mark = "✅ " if n == current else "⚪️ "
#         buttons.append([InlineKeyboardButton(text=f"{mark}{n} изображений", callback_data=f"setm_{n}")])
#     buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_settings")])
#     return InlineKeyboardMarkup(inline_keyboard=buttons)

# @router.message(Command("set"))
# async def cmd_settings(m: Message):
#     async with SessionLocal() as s:
#         user = (await s.execute(select(User).where(User.chat_id == m.from_user.id))).scalar_one_or_none()
#         if not user:
#             await safe_send_text(m.bot, m.chat.id, "Нажмите /start")
#             return
        
#         text = (
#             f"⚙️ <b>Настройки генерации</b>\n\n"
#             f"📊 Текущие:\n"
#             f"├ Качество: <b>{user.image_resolution}</b>\n"
#             f"└ Количество: <b>{user.max_images}</b> изображений\n\n"
#             f"💡 <b>Важно:</b>\n"
#             f"• Качество не влияет на баланс\n"
#             f"• Количество изображений = количество списанных генераций\n"
#             f"  (например, 3 изображения = 3 генерации с баланса)"
#         )
        
#         await safe_send_text(m.bot, m.chat.id, text, reply_markup=kb_settings_menu())

# @router.callback_query(F.data == "set_quality")
# async def cb_set_quality(c: CallbackQuery):
#     await safe_answer(c)
#     async with SessionLocal() as s:
#         user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
#         await safe_edit_text(
#             c.message,
#             f"🎨 <b>Выберите качество изображения</b>\n\n"
#             f"Текущее: <b>{user.image_resolution}</b>\n\n"
#             f"<i>Качество не влияет на стоимость</i>",
#             reply_markup=kb_quality_settings(user.image_resolution)
#         )

# @router.callback_query(F.data.startswith("setq_"))
# async def cb_set_quality_value(c: CallbackQuery):
#     await safe_answer(c)
#     quality = c.data.replace("setq_", "")
#     if quality not in ["1K", "2K", "4K"]:
#         return
    
#     async with SessionLocal() as s:
#         await s.execute(
#             update(User)
#             .where(User.chat_id == c.from_user.id)
#             .values(image_resolution=quality)
#         )
#         await s.commit()
#         user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
    
#     await safe_edit_text(
#         c.message,
#         f"✅ Качество установлено: <b>{quality}</b>\n\n"
#         f"📊 Текущие настройки:\n"
#         f"├ Качество: <b>{user.image_resolution}</b>\n"
#         f"└ Количество: <b>{user.max_images}</b> изображений",
#         reply_markup=kb_settings_menu()
#     )

# @router.callback_query(F.data == "set_max_images")
# async def cb_set_max_images(c: CallbackQuery):
#     await safe_answer(c)
#     async with SessionLocal() as s:
#         user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
#         await safe_edit_text(
#             c.message,
#             f"🖼 <b>Количество изображений в результате</b>\n\n"
#             f"Текущее: <b>{user.max_images}</b>\n\n"
#             f"⚠️ <b>Важно:</b> Количество изображений = количество списанных генераций!\n"
#             f"Например, если выбрать 3 изображения, с баланса спишется 3 генерации.",
#             reply_markup=kb_max_images_settings(user.max_images)
#         )

# @router.callback_query(F.data.startswith("setm_"))
# async def cb_set_max_images_value(c: CallbackQuery):
#     await safe_answer(c)
#     try:
#         max_imgs = int(c.data.replace("setm_", ""))
#         if not 1 <= max_imgs <= 6:
#             return
#     except ValueError:
#         return
    
#     async with SessionLocal() as s:
#         await s.execute(
#             update(User)
#             .where(User.chat_id == c.from_user.id)
#             .values(max_images=max_imgs)
#         )
#         await s.commit()
#         user = (await s.execute(select(User).where(User.chat_id == c.from_user.id))).scalar_one()
    
#     await safe_edit_text(
#         c.message,
#         f"✅ Количество установлено: <b>{max_imgs}</b>\n\n"
#         f"📊 Текущие настройки:\n"
#         f"├ Качество: <b>{user.image_resolution}</b>\n"
#         f"└ Количество: <b>{user.max_images}</b> изображений\n\n"
#         f"💰 При генерации спишется: <b>{max_imgs}</b> генераций",
#         reply_markup=kb_settings_menu()
#     )

# @router.callback_query(F.data == "back_settings")
# async def cb_back_settings(c: CallbackQuery):
#     await safe_answer(c)
#     await cmd_settings(c.message)

# @router.callback_query(F.data == "close_settings")
# async def cb_close_settings(c: CallbackQuery):
#     await safe_answer(c)
#     try:
#         await c.message.delete()
#     except Exception:
#         pass