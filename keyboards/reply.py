from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_kb():
    """Главное меню бота"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти монету"), KeyboardButton(text="⭐ Избранное")],
            [KeyboardButton(text="📊 Индикаторы"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )

def get_coin_actions_kb():
    """Меню, которое появляется после выбора монеты"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⭐ В избранное"), KeyboardButton(text="🔔 Поставить алерт")],
            [KeyboardButton(text="📱 Меню")]
        ],
        resize_keyboard=True
    )
