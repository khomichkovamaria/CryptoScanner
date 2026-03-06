import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
import config
import database # Импортируем весь модуль

bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- API ---
async def get_coin_data(coin_id: str):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id.lower().strip()}"
    params = {"tickers": "false", "market_data": "true", "community_data": "false", "developer_data": "false"}
    headers = {"x-cg-demo-api-key": config.CG_API_KEY} if config.CG_API_KEY else {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "price": data["market_data"]["current_price"]["usd"],
                        "change": data["market_data"]["price_change_percentage_24h"],
                        "ticker": data["symbol"].upper()
                    }
    except: pass
    return None

async def get_multi_rsi(coin_id: str):
    intervals = {"1ч": "1", "4ч": "2", "1д": "14"}
    results = []
    async with aiohttp.ClientSession() as session:
        for label, days in intervals.items():
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {"vs_currency": "usd", "days": days}
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        prices = [p[1] for p in data['prices']]
                        points = prices[-15:]
                        gains = [points[i] - points[i-1] for i in range(1, len(points)) if points[i] - points[i-1] > 0]
                        losses = [abs(points[i] - points[i-1]) for i in range(1, len(points)) if points[i] - points[i-1] < 0]
                        avg_g, avg_l = (sum(gains)/14 if gains else 0), (sum(losses)/14 if losses else 1)
                        rsi = 100 - (100 / (1 + (avg_g / (avg_l or 1))))
                        status = "🔴" if rsi > 70 else "🟢" if rsi < 30 else "⚪️"
                        results.append(f"{status} **{label}**: `{rsi:.1f}`")
            except: results.append(f"⚠️ {label}: ошибка")
    return "\n".join(results) or "Нет данных для анализа"

# --- Клавиатуры ---
def get_main_menu():
    kb = [[types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")], [types.KeyboardButton(text="❓ Помощь")]]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот-аналитик готов! 📈", reply_markup=get_main_menu())

async def send_coin_card(message: types.Message, coin_id: str, edit_message=None):
    data = await get_coin_data(coin_id)
    if data:
        is_fav = await database.is_favorite(message.chat.id, coin_id)
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🗑 Удалить" if is_fav else "⭐ В избранное", callback_data=f"{'rem' if is_fav else 'fav'}_{coin_id}_{data['ticker']}"))
        builder.row(types.InlineKeyboardButton(text="📊 Тех. анализ (RSI)", callback_data=f"tf_{coin_id}"))
        res = f"💰 **{coin_id.upper()} ({data['ticker']})**\n\n💵 Цена: `${data['price']:,.2f}`\n{'📈' if data['change']>=0 else '📉'} 24ч: `{data['change']:.2f}%`"
        if edit_message: await edit_message.edit_text(res, parse_mode="Markdown", reply_markup=builder.as_markup())
        else: await message.answer(res, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        err = f"❌ Монета `{coin_id}` не найдена."
        if edit_message: await edit_message.edit_text(err, parse_mode="Markdown")
        else: await message.answer(err, parse_mode="Markdown")

@dp.message(F.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    favs = await database.get_favorites(message.from_user.id)
    if not favs: return await message.answer("Список избранного пуст.")
    builder = InlineKeyboardBuilder()
    for item in favs:
        # Используем ключи словаря, это на 100% исключает ошибку "одной буквы"
        builder.add(types.InlineKeyboardButton(text=item['ticker'], callback_data=f"price_{item['coin_id']}"))
    builder.adjust(3)
    await message.answer("⭐ Ваше избранное:", reply_markup=builder.as_markup())

@dp.message(F.text == "🔍 Найти монету")
async def find_prompt(message: types.Message):
    await message.answer("Введите ID монеты (напр. `bitcoin`):")

@dp.message()
async def handle_text(message: types.Message):
    if not message.text or message.text in ["🔍 Найти монету", "⭐ Избранное", "❓ Помощь"]: return
    msg = await message.answer(f"🔍 Ищу `{message.text}`...")
    await send_coin_card(message, message.text, edit_message=msg)

@dp.callback_query(F.data.startswith("tf_"))
async def show_analysis(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await callback.answer("📊 Считаю...")
    analysis = await get_multi_rsi(coin_id)
    await callback.message.answer(f"📊 **Анализ {coin_id.upper()}:**\n\n{analysis}", parse_mode="Markdown")

@dp.callback_query(F.data.contains("fav_") or F.data.contains("rem_"))
async def handle_fav(callback: types.CallbackQuery):
    action, coin_id, ticker = callback.data.split("_")
    if action == "fav": await database.add_favorite(callback.from_user.id, coin_id, ticker)
    else: await database.remove_favorite(callback.from_user.id, coin_id)
    await callback.answer("Готово!")
    await send_coin_card(callback.message, coin_id, edit_message=callback.message)

@dp.callback_query(F.data.startswith("price_"))
async def price_call(callback: types.CallbackQuery):
    await callback.answer()
    await send_coin_card(callback.message, callback.data.split("_")[1])

async def main():
    await database.init_db()
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', config.PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
