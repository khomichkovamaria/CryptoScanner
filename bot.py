import os
import asyncio
import requests
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS alerts (user_id INTEGER, target_price REAL, start_price REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, coin_id TEXT)')
    conn.commit()
    conn.close()

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC 🟠"), KeyboardButton(text="ETH 🔵")],
            [KeyboardButton(text="⭐ Мой список"), KeyboardButton(text="📈 Индекс")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот готов! 🚀\n\nКоманды:\n`/alert 75000` — алерт на BTC\n`/add solana` — в список", reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(Command("alert"))
async def set_alert(message: types.Message):
    try:
        target = float(message.text.split()[1])
        res = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()
        current = res['bitcoin']['usd']
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO alerts VALUES (?, ?, ?)', (message.from_user.id, target, current))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Ок! Слежу. Сейчас BTC: ${current:,}. Жду ${target:,}")
    except:
        await message.answer("Пиши так: `/alert 70000`")

@dp.message(Command("add"))
async def add_coin(message: types.Message):
    try:
        coin = message.text.split()[1].lower()
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO favorites VALUES (?, ?)', (message.from_user.id, coin))
        conn.commit()
        conn.close()
        await message.answer(f"⭐ Монета `{coin}` добавлена в список!", parse_mode="Markdown")
    except:
        await message.answer("Пиши так: `/add solana`")

@dp.message()
async def handle_text(message: types.Message):
    text = message.text.lower()
    if "btc" in text:
        res = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()
        await message.answer(f"BTC: ${res['bitcoin']['usd']:,}")
    elif "мой список" in text:
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT coin_id FROM favorites WHERE user_id = ?', (message.from_user.id,))
        coins = [r[0] for r in cursor.fetchall()]
        conn.close()
        if not coins:
            await message.answer("Список пуст! Добавь монеты командой `/add`")
        else:
            ids = ",".join(list(set(coins)))
            data = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd").json()
            res = "📊 **Твой список:**\n"
            for c, v in data.items():
                res += f"• {c.capitalize()}: ${v['usd']:,}\n"
            await message.answer(res, parse_mode="Markdown")
    elif "индекс" in text:
        r = requests.get("https://api.alternative.me/fng/").json()
        await message.answer(f"📈 Индекс: {r['data'][0]['value']}/100")
    else:
        await message.answer("Используй кнопки меню или команды /alert и /add")

async def handle(request): return web.Response(text="OK")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
