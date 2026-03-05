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

def fetch_price(coin_id):
    """Надежное получение цены"""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        headers = {"x-cg-demo-api-key": CG_API_KEY} if CG_API_KEY else {}
        res = requests.get(url, headers=headers, timeout=10).json()
        return res[coin_id]['usd']
    except:
        return None

# --- ФОНОВЫЕ АЛЕРТЫ ---
async def check_alerts_loop():
    while True:
        await asyncio.sleep(60)
        try:
            conn = sqlite3.connect('crypto_bot.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, target_price, start_price FROM alerts")
            alerts = cursor.fetchall()
            
            if alerts:
                current_btc = fetch_price("bitcoin")
                if current_btc:
                    for user_id, target, start in alerts:
                        hit = False
                        if target > start and current_btc >= target: hit = True
                        elif target < start and current_btc <= target: hit = True
                        
                        if hit:
                            await bot.send_message(user_id, f"🔔 **ALERT!**\nBitcoin: `${current_btc:,}`\nТвоя цель `${target:,}` достигнута! 🚀", parse_mode="Markdown")
                            cursor.execute("DELETE FROM alerts WHERE user_id = ? AND target_price = ?", (user_id, target))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Loop error: {e}")

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот готов! Используй кнопки ниже или команды:\n`/alert 75000` — на BTC\n`/add solana` — в список", reply_markup=get_main_keyboard())

@dp.message(Command("alert"))
async def set_alert(message: types.Message):
    try:
        args = message.text.split()
        if len(args) < 2: raise ValueError
        target = float(args[1].replace(',', '.'))
        current = fetch_price("bitcoin")
        
        if current:
            conn = sqlite3.connect('crypto_bot.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO alerts VALUES (?, ?, ?)', (message.from_user.id, target, current))
            conn.commit()
            conn.close()
            verb = "роста" if target > current else "падения"
            await message.answer(f"✅ Ок! Жду {verb} BTC до `${target:,}`\n(Сейчас: `${current:,}`)")
        else:
            await message.answer("❌ Ошибка API. Попробуй позже.")
    except:
        await message.answer("Пиши так: `/alert 72000` (только число)")

@dp.message(Command("add"))
async def add_coin(message: types.Message):
    try:
        coin = message.text.split()[1].lower().strip()
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO favorites VALUES (?, ?)', (message.from_user.id, coin))
        conn.commit()
        conn.close()
        await message.answer(f"⭐ `{coin}` добавлена! Нажми 'Мой список', чтобы проверить.")
    except:
        await message.answer("Пиши так: `/add solana` (название как на CoinGecko)")

# --- ТЕКСТ И КНОПКИ ---
@dp.message()
async def handle_message(message: types.Message):
    msg = message.text.lower()
    
    if "btc" in msg:
        p = fetch_price("bitcoin")
        await message.answer(f"BTC 🟠: `${p:,}`" if p else "Биржа не отвечает...")

    elif "eth" in msg:
        p = fetch_price("ethereum")
        await message.answer(f"ETH 🔵: `${p:,}`" if p else "Биржа не отвечает...")

    elif "индекс" in msg:
        try:
            r = requests.get("https://api.alternative.me/fng/").json()
            val, state = r['data'][0]['value'], r['data'][0]['value_classification']
            await message.answer(f"📈 Индекс: **{val}/100** ({state})", parse_mode="Markdown")
        except:
            await message.answer("Ошибка индекса.")

    elif "мой список" in msg:
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT coin_id FROM favorites WHERE user_id = ?', (message.from_user.id,))
        coins = list(set([r[0] for r in cursor.fetchall()]))
        conn.close()
        
        if not coins:
            await message.answer("Список пуст. Добавь: `/add solana`")
            return

        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coins)}&vs_currencies=usd"
            data = requests.get(url).json()
            res = "📊 **Твой список:**\n\n"
            for c in coins:
                if c in data:
                    res += f"• {c.capitalize()}: `${data[c]['usd']:,}`\n"
                else:
                    res += f"• {c.capitalize()}: (нет данных)\n"
            await message.answer(res, parse_mode="Markdown")
        except:
            await message.answer("Ошибка при загрузке списка.")
    else:
        await message.answer("Используй кнопки меню или /start", reply_markup=get_main_keyboard())

# --- ЗАПУСК ---
async def handle(request): return web.Response(text="OK")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(check_alerts_loop())
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
