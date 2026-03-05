import os
import asyncio
import requests
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('API_TOKEN')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS alerts (user_id INTEGER, coin_id TEXT, target_price REAL, start_price REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, coin_id TEXT)')
    conn.commit()
    conn.close()

# --- РАБОТА С API ---
def fetch_prices(coin_ids):
    try:
        clean_ids = [c.strip().lower() for c in coin_ids if c]
        if not clean_ids: return {}
        ids_str = ",".join(clean_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        logging.error(f"Ошибка API: {e}")
        return {}

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск монеты"), KeyboardButton(text="⭐ Избранное")],
            [KeyboardButton(text="📈 Индекс страха"), KeyboardButton(text="⚙️ Помощь")]
        ], resize_keyboard=True
    )

def get_coin_menu_kb(coin_id, is_fav=False):
    buttons = [
        [InlineKeyboardButton(text="🔔 Добавить алерт", callback_data=f"set_alert_{coin_id}")],
    ]
    if is_fav:
        buttons.append([InlineKeyboardButton(text="❌ Удалить из избранного", callback_data=f"rem_fav_{coin_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="⭐ В избранное", callback_data=f"add_fav_{coin_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("🚀 **CryptoScanner запущен!**\nИспользуй кнопки меню для навигации.", reply_markup=get_main_kb(), parse_mode="Markdown")

@dp.message(F.text == "⚙️ Помощь")
async def help_cmd(message: types.Message):
    await message.answer("📖 **Как пользоваться ботом:**\n\n1. Нажми **Поиск монеты** и напиши её ID (например: `bitcoin`).\n2. В карточке монеты нажми **В избранное**.\n3. Устанавливай алерты через кнопку в меню монеты.", parse_mode="Markdown")

@dp.message(F.text == "📈 Индекс страха")
async def show_fng(message: types.Message):
    try:
        data = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        val = int(data['data'][0]['value'])
        status = data['data'][0]['value_classification']
        await message.answer(f"📈 **Индекс страха и жадности:**\n\nЗначение: `{val}/100`\nСтатус: *{status}*", parse_mode="Markdown")
    except:
        await message.answer("❌ Сервис индекса временно недоступен.")

@dp.message(F.text == "⭐ Избранное")
async def show_favs(message: types.Message):
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT coin_id FROM favorites WHERE user_id = ?', (message.from_user.id,))
    coins = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    if not coins:
        await message.answer("Твой список избранного пока пуст.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📊 {c.upper()}", callback_data=f"view_{c}")] for c in coins
    ])
    await message.answer("⭐ Твои монеты:", reply_markup=kb)

@dp.message(F.text == "🔍 Поиск монеты")
async def search_hint(message: types.Message):
    await message.answer("Напиши ID монеты (например: `bitcoin`, `ethereum`, `solana`)")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА (ПОИСК) ---
@dp.message(F.text)
async def handle_text(message: types.Message):
    # Если это не системная кнопка — ищем монету
    excluded_texts = ["🔍 Поиск монеты", "⭐ Избранное", "📈 Индекс страха", "⚙️ Помощь"]
    if message.text in excluded_texts:
        return

    coin_id = message.text.lower().strip()
    data = fetch_prices([coin_id])
    price = data.get(coin_id, {}).get('usd')
    
    if price is None:
        await message.answer(f"❌ Монета `{coin_id}` не найдена или API недоступно.")
        return

    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM favorites WHERE user_id=? AND coin_id=?', (message.from_user.id, coin_id))
    is_fav = cursor.fetchone() is not None
    conn.close()

    await message.answer(
        f"💰 **{coin_id.upper()}**\nЦена: `${price:,.2f}`", 
        reply_markup=get_coin_menu_kb(coin_id, is_fav),
        parse_mode="Markdown"
    )

# --- CALLBACKS (КНОПКИ) ---
@dp.callback_query(F.data.startswith("view_"))
async def cb_view(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    # Эмулируем текстовый ввод для показа карточки
    callback.message.text = coin_id
    await handle_text(callback.message)
    await callback.answer()

@dp.callback_query(F.data.startswith("add_fav_"))
async def cb_add_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO favorites (user_id, coin_id) VALUES (?, ?)', (callback.from_user.id, coin_id))
    conn.commit()
    conn.close()
    await callback.answer(f"✅ {coin_id.upper()} в избранном!")
    # Обновляем сообщение, чтобы кнопка сменилась на "Удалить"
    await cb_view(callback)

@dp.callback_query(F.data.startswith("rem_fav_"))
async def cb_rem_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM favorites WHERE user_id=? AND coin_id=?', (callback.from_user.id, coin_id))
    conn.commit()
    conn.close()
    await callback.answer("❌ Удалено")
    await cb_view(callback)

# --- ЗАПУСК ---
async def handle(request): return web.Response(text="OK")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
