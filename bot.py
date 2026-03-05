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
    await message.answer("Бот запущен! 🚀\n`/alert 70000` - алерт на BTC\n`/add solana` - в список", reply_markup=get_main_keyboard())

@dp.message()
async def handle_all(message: types.Message):
    text = message.text.lower()
    if "btc" in text:
        try:
            res = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", headers={"x-cg-demo-api-key": CG_API_KEY}).json()
            price = res['bitcoin']['usd']
            await message.answer(f"BTC: ${price:,}")
        except:
            await message.answer("Ошибка связи с биржей")
    elif "индекс" in text:
        try:
            res = requests.get("https://api.alternative.me/fng/").json()
            val = res['data'][0]['value']
            await message.answer(f"📈 Индекс страха: {val}/100")
        except:
            await message.answer("Ошибка получения индекса")
    else:
        await message.answer("Используй кнопки меню", reply_markup=get_main_keyboard())

async def handle(request):
    return web.Response(text="Бот активен")

async def main():
    init_db()
    # Чистим старые подключения, чтобы не было ошибки Conflict
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
