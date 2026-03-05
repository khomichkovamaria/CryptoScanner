import os
import asyncio
import requests
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    # Таблица для алертов: ID юзера, цель, цена в момент установки
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts 
                      (user_id INTEGER, target_price REAL, start_price REAL)''')
    # Таблица для избранного: ID юзера, ID монеты
    cursor.execute('''CREATE TABLE IF NOT EXISTS favorites 
                      (user_id INTEGER, coin_id TEXT)''')
    conn.commit()
    conn.close()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_crypto_data(coin_ids):
    """Получает данные по списку монет (через запятую)"""
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_ids}&vs_currencies=usd&include_24hr_change=true"
    headers = {"x-cg-demo-api-key": CG_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Ошибка API: {e}")
        return None

def get_main_keyboard():
    buttons = [
        [KeyboardButton(text="BTC 🟠"), KeyboardButton(text="ETH 🔵")],
        [KeyboardButton(text="⭐ Мой список"), KeyboardButton(text="📈 Индекс")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ЛОГИКА АЛЕРТОВ ---
async def check_alerts_loop():
    while True:
        await asyncio.sleep(60) # Проверка раз в минуту
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, target_price, start_price FROM alerts")
        all_alerts = cursor.fetchall()
        
        if all_alerts:
            # Для простоты проверяем пока только BTC в алертах
            data = get_crypto_data("bitcoin")
            if data:
                current_price = data['bitcoin']['usd']
                for user_id, target, start in all_alerts:
                    is_hit = False
                    msg = ""
                    
                    if target > start and current_price >= target: # Ждали роста
                        is_hit = True
                        msg = f"🚀 **ЦЕЛЬ ДОСТИГНУТА (РОСТ)!**\nBitcoin: `${current_price:,}`\nТвой порог `${target:,}` пробит вверх!"
                    elif target < start and current_price <= target: # Ждали падения
                        is_hit = True
                        msg = f"📉 **ЦЕЛЬ ДОСТИГНУТА (ПАДЕНИЕ)!**\nBitcoin: `${current_price:,}`\nТвой порог `${target:,}` достигнут!"
                    
                    if is_hit:
                        await bot.send_message(user_id, msg, parse_mode="Markdown")
                        cursor.execute("DELETE FROM alerts WHERE user_id = ? AND target_price = ?", (user_id, target))
        conn.commit()
        conn.close()

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Бот обновлен!\n\n"
        "📍 `/alert 75000` — поставить уведомление на BTC\n"
        "📍 `/add solana` — добавить монету в Избранное",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("alert"))
async def
