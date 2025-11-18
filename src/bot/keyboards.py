# from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
# from services.pricing import PACKS_RUB, credits_for_rub


# ASPECT_RATIOS = {
#     "21:9": "21:9 (Ultrawide)",
#     "16:9": "16:9 (Wide)",
#     "4:3": "4:3 (Landscape)",
#     "3:2": "3:2 (Landscape)",
#     "1:1": "1:1 (Square)",
#     "9:16": "9:16 (Portrait)",
#     "3:4": "3:4 (Portrait)",
#     "2:3": "2:3 (Portrait)",
#     "5:4": "5:4 (Flexible)",
#     "4:5": "4:5 (Flexible)",
# }

# def kb_quality_selector(current_quality: str = "1K") -> InlineKeyboardMarkup:
#     """Клавиатура выбора качества изображения с галочками"""
#     buttons = []
    
#     qualities = {
#         "1K": "1K - Быстро",
#         "2K": "2K - Стандарт",
#         "4K": "4K - Максимум",
#     }
    
#     for quality_key, quality_label in qualities.items():
#         # ✅ Галочка остаётся на выбранном качестве
#         checkmark = "✅ " if quality_key == current_quality else "⚪️ "
#         buttons.append([
#             InlineKeyboardButton(
#                 text=f"{checkmark}{quality_label}",
#                 callback_data=f"quality_{quality_key}"
#             )
#         ])
    
#     return InlineKeyboardMarkup(inline_keyboard=buttons)

# def validate_aspect_ratio(ar: str) -> bool:
#     """Проверка валидности соотношения сторон"""
#     if not ar:
#         return False
#     return ar in ASPECT_RATIOS

# def kb_aspect_ratio_selector() -> InlineKeyboardMarkup:
#     """Клавиатура выбора соотношения сторон"""
#     buttons = []
#     buttons.append([
#         InlineKeyboardButton(text="📱 Вертикальное (9:16)", callback_data="ar_9:16"),
#     ])
#     buttons.append([
#         InlineKeyboardButton(text="🖼 Горизонтальное (16:9)", callback_data="ar_16:9"),
#     ])
#     # buttons.append([InlineKeyboardButton(text="⏩ Пропустить (авто)", callback_data="ar_skip")])
    
#     return InlineKeyboardMarkup(inline_keyboard=buttons)

# def kb_topup_packs() -> InlineKeyboardMarkup:
#     rows = []
#     for rub in PACKS_RUB:
#         cr = credits_for_rub(rub)
#         rows.append([InlineKeyboardButton(text=f"{rub} ₽ → {cr} генераций", callback_data=f"pack_{rub}")])
#     rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_methods")])
#     return InlineKeyboardMarkup(inline_keyboard=rows)

# def kb_topup_stars() -> InlineKeyboardMarkup:
#     rows = []
#     for stars in PACKS_RUB:
#         cr = credits_for_rub(stars)
#         rows.append([
#             InlineKeyboardButton(
#                 text=f"{stars} ⭐ → {cr} генераций",
#                 callback_data=f"stars_{stars}"
#             )
#         ])
#     rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_methods")])
#     return InlineKeyboardMarkup(inline_keyboard=rows)

# def kb_topup_methods() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [
#             InlineKeyboardButton(text="💳 Карта РФ(₽)", callback_data="m_rub"),
#             InlineKeyboardButton(text="⭐️ Звёзды", callback_data="m_stars"),
#         ],
#     ])

# def kb_receipt_choice() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="📧 Отправить чек на e-mail", callback_data="receipt_need")],
#         [InlineKeyboardButton(text="🙅 Чек не нужен", callback_data="receipt_skip")],
#         [InlineKeyboardButton(text="↩️ Назад", callback_data="back_methods")],
#     ])

# def kb_gen_step_back() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_images")],
#     ])

# def kb_final_result() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="🖼 Начать заново", callback_data="new_image")],
#         [InlineKeyboardButton(text="🔁 Сгенерировать похожее", callback_data="regenerate")],
#     ])

# def kb_create_image() -> InlineKeyboardMarkup:
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Создать изображение", callback_data="create_image")],
#     ])
    
# # def kb_gen_step_back(vertical: bool = True) -> InlineKeyboardMarkup:
# #     """Клавиатура с переключателем ориентации"""
# #     checkbox = "✅" if vertical else "☑️"
# #     text = f"{checkbox} Вертикально" if vertical else f"{checkbox} Горизонтально"
    
# #     return InlineKeyboardMarkup(
# #         inline_keyboard=[
# #             [InlineKeyboardButton(text=text, callback_data=f"toggle_orientation_{vertical}")]
# #         ]
# #     )    
    
# def kb_gen_step_back() -> InlineKeyboardMarkup:
#     """Клавиатура для возврата к загрузке фото"""
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_images")]
#         ]
#     )    


# def kb_edit_orientation_selector() -> InlineKeyboardMarkup:
#     """Выбор ориентации для редактирования"""
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [
#             InlineKeyboardButton(text="✅ Вертикально (9:16)", callback_data="edit_or_9:16"),
#             InlineKeyboardButton(text="⚪️ Горизонтально (16:9)", callback_data="edit_or_16:9"),
#         ]
#     ])    

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.pricing import PACKS_RUB, credits_for_rub


ASPECT_RATIOS = {
    "21:9": "21:9 (Ultrawide)",
    "16:9": "16:9 (Wide)",
    "4:3": "4:3 (Landscape)",
    "3:2": "3:2 (Landscape)",
    "1:1": "1:1 (Square)",
    "9:16": "9:16 (Portrait)",
    "3:4": "3:4 (Portrait)",
    "2:3": "2:3 (Portrait)",
    "5:4": "5:4 (Flexible)",
    "4:5": "4:5 (Flexible)",
}

def kb_quality_selector(current_quality: str = "1K") -> InlineKeyboardMarkup:
    """Клавиатура выбора качества изображения с галочками"""
    buttons = []
    
    qualities = {
        "1K": "1K - Быстро",
        "2K": "2K - Стандарт",
        "4K": "4K - Максимум",
    }
    
    for quality_key, quality_label in qualities.items():
        checkmark = "✅ " if quality_key == current_quality else "⚪️ "
        buttons.append([
            InlineKeyboardButton(
                text=f"{checkmark}{quality_label}",
                callback_data=f"quality_{quality_key}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def validate_aspect_ratio(ar: str) -> bool:
    """Проверка валидности соотношения сторон"""
    if not ar:
        return False
    return ar in ASPECT_RATIOS

def kb_aspect_ratio_selector() -> InlineKeyboardMarkup:
    """Клавиатура выбора соотношения сторон"""
    buttons = []
    buttons.append([
        InlineKeyboardButton(text="📱 Вертикальное (9:16)", callback_data="ar_9:16"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🖼 Горизонтальное (16:9)", callback_data="ar_16:9"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# 🆕 НОВАЯ ФУНКЦИЯ для /edit
def kb_edit_orientation_selector(current: str = "9:16") -> InlineKeyboardMarkup:
    """Клавиатура выбора ориентации для редактирования (Edit mode)"""
    vertical_mark = "✅" if current == "9:16" else "⚪️"
    horizontal_mark = "✅" if current == "16:9" else "⚪️"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{vertical_mark} Вертикально", 
                callback_data="edit_or_9:16"
            ),
            InlineKeyboardButton(
                text=f"{horizontal_mark} Горизонтально", 
                callback_data="edit_or_16:9"
            ),
        ]
    ])

def kb_topup_packs() -> InlineKeyboardMarkup:
    rows = []
    for rub in PACKS_RUB:
        cr = credits_for_rub(rub)
        rows.append([InlineKeyboardButton(text=f"{rub} ₽ → {cr} генераций", callback_data=f"pack_{rub}")])
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_methods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_topup_stars() -> InlineKeyboardMarkup:
    rows = []
    for stars in PACKS_RUB:
        cr = credits_for_rub(stars)
        rows.append([
            InlineKeyboardButton(
                text=f"{stars} ⭐ → {cr} генераций",
                callback_data=f"stars_{stars}"
            )
        ])
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_methods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_topup_methods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Карта РФ(₽)", callback_data="m_rub"),
            InlineKeyboardButton(text="⭐️ Звёзды", callback_data="m_stars"),
        ],
    ])

def kb_receipt_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Отправить чек на e-mail", callback_data="receipt_need")],
        [InlineKeyboardButton(text="🙅 Чек не нужен", callback_data="receipt_skip")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_methods")],
    ])

def kb_gen_step_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_images")],
    ])

def kb_final_result() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Начать заново", callback_data="new_image")],
        [InlineKeyboardButton(text="🔁 Сгенерировать похожее", callback_data="regenerate")],
    ])

def kb_create_image() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать изображение", callback_data="create_image")],
    ])