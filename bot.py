import os
import asyncio
import requests
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# Настраиваем логи, чтобы видеть ошибки в панели Render
logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts 
                      (user_id INTEGER, target_price REAL, start_price REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS favorites 
                      (user_id INTEGER, coin_id TEXT)''')
    conn.commit()
    conn.close()

# --- ФУНКЦИИ ---
def get_crypto_data(coin_ids):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_ids}&vs_currencies=usd&include_24hr_change=true"
    headers = {"x-cg-demo-api-key": CG_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except:
        return None

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC 🟠"), KeyboardButton(text="ETH 🔵")],
            [KeyboardButton(text="⭐ Мой список"), KeyboardButton(text="📈 Индекс")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

# --- ФОНОВАЯ ПРОВЕРКА ---
async def check_alerts_loop():
    while True:
        await asyncio.sleep(60)
        try:
            conn = sqlite3.connect('crypto_bot.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, target_price, start_price FROM alerts")
            all_alerts = cursor.fetchall()
            
            if all_alerts:
                data = get_crypto_data("bitcoin")
                if data:
                    current_price = data['bitcoin']['usd']
                    for user_id, target, start in all_alerts:
                        msg = ""
                        if target > start and current_price >= target:
                            msg = f"🚀 **ЦЕЛЬ ДОСТИГНУТА!**\nBTC вырос до `${current_price:,}`"
                        elif target < start and current_price <= target:
                            msg = f"📉 **ЦЕЛЬ ДОСТИГНУТА!**\nBTC упал до `${current_price:,}`"
                        
                        if msg:
                            await bot.send_message(user_id, msg, parse_mode="Markdown")
                            cursor.execute("DELETE FROM alerts WHERE user_id = ? AND target_price = ?", (user_id, target))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Ошибка в цикле алертов: {e}")

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот готов! Используй кнопки или команды:\n`/alert цена` — уведомление на BTC\n`/add монета` — в избранное", reply_markup=get_main_keyboard())

@dp.message(Command("alert"))
async def set_alert(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2: raise ValueError
        target = float(parts[1])
        data = get_crypto_data("bitcoin")
        start_p = data['bitcoin']['usd']
        
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alerts VALUES (?, ?, ?)", (message.from_user.id, target, start_p))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Ок! Слежу за BTC. Цель: ${target:,}")
    except:
        await message.answer("Ошибка! Напиши например: `/alert 75000`")

@dp.message(Command("add"))
async def add_fav(message: types.Message):
    coin_id = message.text.replace("/add ", "").lower().strip()
    if coin_id == "/add": return
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO favorites VALUES (?, ?)", (message.from_user.id, coin_id))
    conn.commit()
    conn.close()
    await message.answer(f"⭐ `{coin_id}` в твоем списке!")

@dp.message()
async def handle_text(message: types.Message):
    text = message.text.lower()
    if "мой список" in text:
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT coin_id FROM favorites WHERE user_id = ?", (message.from_user.id,))
        favs = list(set([row[0] for row in cursor.fetchall()])) # Убираем дубликаты
        conn.close()
        
        if not favs:
            await message.answer("Список пуст! Добавь: `/add solana`")
            return
            
        data = get_crypto_data(",".join(favs))
        if data:
            res = "📊 **Избранное:**\n"
            for c, v in data.items():
                res += f"• {c.capitalize()}: `${v['usd']:,}`\n"
            await message.answer(res, parse_mode="Markdown")
            
    elif "btc" in text:
        d = get_crypto_data("bitcoin")
        if d: await message.answer(f
