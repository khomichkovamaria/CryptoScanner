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

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS alerts (user_id INTEGER, target_price REAL, start_price REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, coin_id TEXT)')
    conn.commit()
    conn.close()

# --- КЛАВИАТУРА ---
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC 🟠"), KeyboardButton(text="ETH 🔵")],
            [KeyboardButton(text="⭐ Мой список"), KeyboardButton(text="📈 Индекс")]
        ],
        resize_keyboard=True
    )

# --- ФОНОВАЯ ПРОВЕРКА АЛЕРТОВ ---
async def check_alerts_loop():
    while True:
        await asyncio.sleep(60) # Проверяем раз в минуту
        try:
            conn = sqlite3.connect('crypto_bot.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, target_price, start_price FROM alerts")
            all_alerts = cursor.fetchall()
            
            if all_alerts:
                res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()
                current_price = res['bitcoin']['usd']
                
                for user_id, target, start in all_alerts:
                    msg = ""
                    # Если ждали роста
                    if target > start and current_price >= target:
                        msg = f"🚀 **ЦЕЛЬ ДОСТИГНУТА!**\nBTC вырос до `${current_price:,}`"
                    # Если ждали падения
                    elif target < start and current_price <= target:
                        msg = f"📉 **ЦЕЛЬ ДОСТИГНУТА!**\nBTC упал до `${current_price:,}`"
                    
                    if msg:
                        await bot.send_message(user_id, msg, parse_mode="Markdown")
                        cursor.execute("DELETE FROM alerts WHERE user_id = ? AND target_price = ?", (user_id, target))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Ошибка в цикле алертов: {e}")

# --- ОБРАБОТЧИКИ КОМАНД ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот готов! 🚀\n\nИспользуй кнопки или команды:\n`/alert 70000` — уведомление на BTC\n`/add solana` — добавить в список", reply_markup=get_main_keyboard())

@dp.message(Command("alert"))
async def set_alert(message: types.Message):
    try:
        target = float(message.text.split()[1])
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()
        current = res['bitcoin']['usd']
        
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO alerts VALUES (?, ?, ?)', (message.from_user.id, target, current))
        conn.commit()
        conn.close()
        
        direction = "роста" if target > current else "падения"
        await message.answer(f"✅ Ок! Жду {direction} BTC до ${target:,}")
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
        await message.answer(f"⭐ Монета `{coin}` добавлена в твой список!", parse_mode="Markdown")
    except:
        await message.answer("Пиши так: `/add solana` (название как на CoinGecko)")

# --- ОБРАБОТКА ТЕКСТА И КНОПОК ---
@dp.message()
async def handle_text(message: types.Message):
    text = message.text.lower()
    
    if "btc" in text:
        data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()
        await message.answer(f"BTC 🟠: `${data['bitcoin']['usd']:,}`", parse_mode="Markdown")

    elif "eth" in text:
        data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd").json()
        await message.answer(f"ETH 🔵: `${data['ethereum']['usd']:,}`", parse_mode="Markdown")

    elif "мой список" in text:
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT coin_id FROM favorites WHERE user_id = ?', (message.from_user.id,))
        coins = list(set([r[0] for r in cursor.fetchall()]))
        conn.close()
        
        if not coins:
            await message.answer("Список пуст! Добавь монеты: `/add solana`")
            return

        try:
            ids = ",".join(coins)
            data = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd").json()
            res_text = "📊 **Твой список:**\n\n"
            for c_id, val in data.items():
                res_text += f"• {c_id.capitalize()}: `${val['usd']:,}`\n"
            await message.answer(res_text, parse_mode="Markdown")
        except:
            await message.answer("Не удалось получить данные. Проверь названия монет.")

    elif "индекс" in text:
        r = requests.get("https://api.alternative.me/fng/").json()
        val = r['data'][0]['value']
        status = r['data'][0]['value_classification']
        await message.answer(f"📈 Индекс: **{val}/100** ({status})", parse_mode="Markdown")

    else:
        await message.answer("Я тебя не понял. Используй кнопки или /start", reply_markup=get_main_keyboard())

# --- СЕРВЕР И ЗАПУСК ---
async def handle(request): return web.Response(text="OK")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(check_alerts_loop()) # Запуск алертов в фоне
    
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080))).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
