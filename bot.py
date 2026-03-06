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

# --- API Логика ---

async def get_coin_data(coin_id: str):
    """Получает текущую цену, изменение и тикер монеты."""
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
                return None
    except:
        return None

async def get_multi_rsi(coin_id: str):
    """Считает RSI сразу для 1ч, 4ч и 1д."""
    intervals = {"1ч": "1", "4ч": "2", "1д": "14"}
    results = []
    async with aiohttp.ClientSession() as session:
        for label, days in intervals.items():
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {"vs_currency": "usd", "days": days}
            try:
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    prices = [p[1] for p in data['prices']]
                    # Берем последние 15 точек для расчета
                    points = prices[-15:] if len(prices) > 15 else prices
                    gains = [points[i] - points[i-1] for i in range(1, len(points)) if points[i] - points[i-1] > 0]
                    losses = [abs(points[i] - points[i-1]) for i in range(1, len(points)) if points[i] - points[i-1] < 0]
                    avg_g, avg_l = (sum(gains)/14 if gains else 0), (sum(losses)/14 if losses else 1)
                    rsi = 100 - (100 / (1 + (avg_g / (avg_l or 1))))
                    status = "🔴" if rsi > 70 else "🟢" if rsi < 30 else "⚪️"
                    results.append(f"{status} **{label}**: `{rsi:.1f}`")
            except:
                results.append(f"⚠️ {label}: ошибка")
    return "\n".join(results)

# --- Клавиатуры ---

def get_main_menu():
    kb = [
        [types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")],
        [types.KeyboardButton(text="📊 Индикаторы"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот-аналитик запущен! 📈 Используйте меню ниже:", reply_markup=get_main_menu())

# --- Основная логика карточки монеты ---

async def send_coin_card(message: types.Message, coin_id: str, edit_message=None):
    data = await get_coin_data(coin_id)
    if data:
        is_fav = await is_favorite(message.chat.id, coin_id)
        builder = InlineKeyboardBuilder()
        # Кнопка добавить/удалить
        builder.row(types.InlineKeyboardButton(
            text="🗑 Удалить из избранного" if is_fav else "⭐ В избранное", 
            callback_data=f"{'rem' if is_fav else 'fav'}_{coin_id}_{data['ticker']}")
        )
        # Кнопка анализа
        builder.row(types.InlineKeyboardButton(text="📊 Тех. анализ (RSI)", callback_data=f"tf_{coin_id}"))

        res = (
            f"💰 **{coin_id.upper()} ({data['ticker']})**\n\n"
            f"💵 Цена: `${data['price']:,.2f}`\n"
            f"{'📈' if data['change']>=0 else '📉'} 24ч: `{data['change']:.2f}%`"
        )
        
        if edit_message:
            await edit_message.edit_text(res, parse_mode="Markdown", reply_markup=builder.as_markup())
        else:
            await message.answer(res, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        err_text = "❌ Монета не найдена. Убедитесь в правильности ID (напр. `bitcoin`)."
        if edit_message: await edit_message.edit_text(err_text)
        else: await message.answer(err_text)

# --- Обработка меню ---

@dp.message(F.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    favs = await get_favorites(message.from_user.id)
    if not favs:
        return await message.answer("Ваш список избранного пока пуст.")
    
    builder = InlineKeyboardBuilder()
    for row in favs:
        # Защита от старых данных: проверяем, пришел ли кортеж (id, ticker)
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            c_id, ticker = row[0], row[1]
        else:
            c_id = row[0] if isinstance(row, (list, tuple)) else row
            ticker = c_id.upper()
        
        builder.add(types.InlineKeyboardButton(text=ticker, callback_data=f"price_{c_id}"))
    
    builder.adjust(3) # Кнопки по 3 в ряд
    await message.answer("⭐ Ваше избранное:", reply_markup=builder.as_markup())

@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    await message.answer("Введите ID монеты латиницей (например, `polkadot`).\nВ 'Избранном' вы можете быстро смотреть курсы ваших монет.")

@dp.message(F.text == "📊 Индикаторы")
async def cmd_indicators_global(message: types.Message):
    await message.answer("Чтобы увидеть индикаторы, найдите нужную монету или выберите её в 'Избранном', затем нажмите кнопку '📊 Тех. анализ'.")

@dp.message(F.text == "🔍 Найти монету")
async def find_prompt(message: types.Message):
    await message.answer("Введите ID монеты (напр. `solana`):")

# --- Обработка текстовых запросов ---

@dp.message()
async def handle_text(message: types.Message):
    if not message.text or message.text.startswith("/") or message.text in ["🔍 Найти монету", "⭐ Избранное", "📊 Индикаторы", "❓ Помощь"]:
        return
    msg = await message.answer(f"🔍 Ищу `{message.text}`...")
    await send_coin_card(message, message.text, edit_message=msg)

# --- Callbacks ---

@dp.callback_query(F.data.startswith("tf_"))
async def show_analysis(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await callback.answer("📊 Считаю индикаторы...")
    analysis = await get_multi_rsi(coin_id)
    await callback.message.answer(f"📊 **Анализ {coin_id.upper()}:**\n\n{analysis}\n\n📍 *30 - Перепроданность, 70 - Перекупленность*", parse_mode="Markdown")

@dp.callback_query(F.data.contains("fav_") or F.data.contains("rem_"))
async def handle_fav_action(callback: types.CallbackQuery):
    data_parts = callback.data.split("_")
    action, coin_id = data_parts[0], data_parts[1]
    ticker = data_parts[2] if len(data_parts) > 2 else coin_id.upper()
    
    if action == "fav":
        await add_favorite(callback.from_user.id, coin_id, ticker)
        await callback.answer(f"✅ {ticker} добавлен!")
    else:
        await remove_favorite(callback.from_user.id, coin_id)
        await callback.answer(f"🗑 {ticker} удален!")
    
    await send_coin_card(callback.message, coin_id, edit_message=callback.message)

@dp.callback_query(F.data.startswith("price_"))
async def price_from_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await send_coin_card(callback.message, coin_id)
    await callback.answer()

# --- Запуск ---

async def handle_web(request):
    return web.Response(text="Bot is live")

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
