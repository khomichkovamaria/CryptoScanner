import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
import config
from database import init_db, add_favorite, get_favorites, is_favorite, remove_favorite

bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Вспомогательная функция для получения цен ---
async def get_coin_price(coin_id: str):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id.lower().strip(),
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    headers = {"x-cg-demo-api-key": config.CG_API_KEY} if config.CG_API_KEY else {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    c_id = coin_id.lower().strip()
                    if c_id in data:
                        return data[c_id]["usd"], data[c_id].get("usd_24h_change", 0)
                return None, None
    except:
        return None, None

# --- Главное меню ---
def get_main_menu():
    kb = [
        [types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")],
        [types.KeyboardButton(text="📊 Индикаторы"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- Команды ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот готов! Выберите действие в меню:", reply_markup=get_main_menu())

# --- ИСПРАВЛЕННАЯ ПОМОЩЬ ---
@dp.message(F.text == "❓ Помощь")
async def cmd_help_text(message: types.Message):
    await message.answer(
        "💡 **Инструкция:**\n\n"
        "• Чтобы узнать курс, просто напишите ID монеты (например: `bitcoin`).\n"
        "• Кнопка «В избранное» сохранит монету в вашу базу.\n"
        "• В разделе ⭐ Избранное можно быстро проверять свои монеты.",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📊 Индикаторы")
async def cmd_indicators(message: types.Message):
    await message.answer("📊 Раздел индикаторов находится в разработке!")

@dp.message(F.text == "🔍 Найти монету")
async def find_prompt(message: types.Message):
    await message.answer("Введите ID монеты (например: `ethereum`, `solana`):")

# --- Универсальная функция карточки монеты ---
async def send_coin_card(message: types.Message, coin_id: str, edit_message=None):
    price, change = await get_coin_price(coin_id)
    if price is not None:
        # Проверяем базу для конкретного пользователя
        user_id = message.chat.id # Для callback-сообщений берем id чата
        already_fav = await is_favorite(user_id, coin_id)
        
        builder = InlineKeyboardBuilder()
        if already_fav:
            builder.row(types.InlineKeyboardButton(text="❌ Удалить из избранного", callback_data=f"rem_{coin_id}"))
        else:
            builder.row(types.InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav_{coin_id}"))

        emoji = "📈" if change >= 0 else "📉"
        formatted_price = f"{price:,.2f}" if price >= 1 else f"{price:.6f}"
        
        res = f"💰 **{coin_id.upper()}**\n\n💵 Цена: `${formatted_price}`\n{emoji} 24ч: `{change:.2f}%`"
        
        if edit_message:
            await edit_message.edit_text(res, parse_mode="Markdown", reply_markup=builder.as_markup())
        else:
            await message.answer(res, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        err = f"❌ Монета `{coin_id}` не найдена."
        if edit_message: await edit_message.edit_text(err)
        else: await message.answer(err)

# --- Раздел Избранное ---
@dp.message(F.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    favs = await get_favorites(message.from_user.id)
    if not favs:
        await message.answer("Ваш список избранного пока пуст.")
        return
    
    builder = InlineKeyboardBuilder()
    unique_favs = list(dict.fromkeys(favs)) # Убираем дубликаты
    for coin in unique_favs:
        builder.row(types.InlineKeyboardButton(text=f"💰 {coin.capitalize()}", callback_data=f"price_{coin}"))
    
    await message.answer("⭐ Ваше избранное (нажмите для проверки цены):", reply_markup=builder.as_markup())

# --- Обработка текста ---
@dp.message()
async def handle_text_input(message: types.Message):
    # Исключаем системные кнопки
    if not message.text or message.text.startswith("/") or message.text in ["🔍 Найти монету", "⭐ Избранное", "📊 Индикаторы", "❓ Помощь"]:
        return
    
    coin_id = message.text.strip().lower()
    msg_wait = await message.answer(f"🔍 Ищу `{coin_id}`...")
    await send_coin_card(message, coin_id, edit_message=msg_wait)

# --- Callbacks (Нажатия на инлайн-кнопки) ---
@dp.callback_query(F.data.startswith("price_"))
async def check_fav_price(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    # Присылаем карточку, где будет кнопка "Удалить"
    await send_coin_card(callback.message, coin_id)
    await callback.answer()

@dp.callback_query(F.data.startswith("fav_"))
async def add_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await add_favorite(callback.from_user.id, coin_id)
    await callback.answer(f"✅ {coin_id.capitalize()} добавлен!")
    await send_coin_card(callback.message, coin_id, edit_message=callback.message)

@dp.callback_query(F.data.startswith("rem_"))
async def rem_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await remove_favorite(callback.from_user.id, coin_id)
    await callback.answer(f"🗑 Удалено!")
    await send_coin_card(callback.message, coin_id, edit_message=callback.message)

# --- Web-сервер и запуск ---
async def handle_web(request):
    return web.Response(text="OK")

async def main():
    await init_db()
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', config.PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
