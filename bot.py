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

async def get_coin_price(coin_id: str):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id.lower().strip(), "vs_currencies": "usd", "include_24hr_change": "true"}
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
    except: return None, None

def get_main_menu():
    kb = [
        [types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")],
        [types.KeyboardButton(text="📊 Индикаторы"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот готов! Выберите действие:", reply_markup=get_main_menu())

# --- ИЗБРАННОЕ КАК КНОПКИ ---
@dp.message(F.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    favs = await get_favorites(message.from_user.id)
    if not favs:
        await message.answer("Список избранного пуст.")
        return
    
    builder = InlineKeyboardBuilder()
    for coin in favs:
        # Каждая монета — это кнопка, при нажатии на которую бот пришлет её цену
        builder.row(types.InlineKeyboardButton(text=f"💰 {coin.capitalize()}", callback_data=f"price_{coin}"))
    
    await message.answer("⭐ Ваше избранное (нажмите на монету для проверки цены):", reply_markup=builder.as_markup())

# --- ИНДИКАТОРЫ ---
@dp.message(F.text == "📊 Индикаторы")
async def cmd_indicators(message: types.Message):
    await message.answer("📊 Раздел индикаторов (RSI, MACD) будет доступен в следующей версии!")

@dp.message(F.text == "🔍 Найти монету")
async def find_prompt(message: types.Message):
    await message.answer("Введите ID монеты (напр. `bitcoin`):", parse_mode="Markdown")

# --- ОБРАБОТКА ЦЕНЫ С УМНОЙ КНОПКОЙ ---
@dp.message()
async def handle_coin(message: types.Message):
    if not message.text or message.text.startswith("/") or message.text in ["❓ Помощь"]: return
    
    coin_id = message.text.strip().lower()
    msg_wait = await message.answer(f"🔍 Ищу `{coin_id}`...")
    
    price, change = await get_coin_price(coin_id)
    if price is not None:
        # Проверяем, в избранном ли монета
        already_fav = await is_favorite(message.from_user.id, coin_id)
        
        builder = InlineKeyboardBuilder()
        if already_fav:
            builder.row(types.InlineKeyboardButton(text="❌ Удалить из избранного", callback_data=f"rem_{coin_id}"))
        else:
            builder.row(types.InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav_{coin_id}"))

        emoji = "📈" if change >= 0 else "📉"
        res = f"💰 **{coin_id.upper()}**\n\n💵 Цена: `${price:,.2f}`\n{emoji} 24ч: `{change:.2f}%`"
        await msg_wait.edit_text(res, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await msg_wait.edit_text("❌ Не найдено.")

# --- CALLBACKS (Нажатия на кнопки) ---
@dp.callback_query(F.data.startswith("fav_"))
async def add_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await add_favorite(callback.from_user.id, coin_id)
    await callback.answer(f"✅ {coin_id.capitalize()} добавлен!")
    # Меняем кнопку на "Удалить"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="❌ Удалить из избранного", callback_data=f"rem_{coin_id}"))
    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("rem_"))
async def rem_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await remove_favorite(callback.from_user.id, coin_id)
    await callback.answer(f"🗑 Удалено!")
    # Меняем кнопку на "Добавить"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav_{coin_id}"))
    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("price_"))
async def check_fav_price(callback: types.CallbackQuery):
    """Позволяет узнать цену прямо из списка избранного."""
    coin_id = callback.data.split("_")[1]
    price, change = await get_coin_price(coin_id)
    if price:
        emoji = "📈" if change >= 0 else "📉"
        await callback.message.answer(f"💰 **{coin_id.upper()}**\nЦена: `${price:,.2f}`\n{emoji} `{change:.2f}%`", parse_mode="Markdown")
    await callback.answer()

async def main():
    await init_db()
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', config.PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
