import os
import asyncio
import requests
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
    cursor.execute('CREATE TABLE IF NOT EXISTS alerts (user_id INTEGER, coin_id TEXT, target_price REAL, start_price REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, coin_id TEXT)')
    conn.commit()
    conn.close()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def fetch_prices(coin_ids):
    try:
        ids = ",".join(coin_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
        return requests.get(url, timeout=10).json()
    except:
        return {}

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск монеты"), KeyboardButton(text="⭐ Избранное")],
            [KeyboardButton(text="📈 Индекс страха"), KeyboardButton(text="⚙️ Помощь")]
        ], resize_keyboard=True
    )

def get_coin_actions_kb(coin_id, is_fav=False):
    buttons = [
        [InlineKeyboardButton(text="🔔 Добавить алерт", callback_data=f"set_alert_{coin_id}")],
    ]
    if is_fav:
        buttons.append([InlineKeyboardButton(text="❌ Удалить из избранного", callback_data=f"rem_fav_{coin_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="⭐ В избранное", callback_data=f"add_fav_{coin_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ФОНОВЫЕ АЛЕРТЫ ---
async def check_alerts_loop():
    while True:
        await asyncio.sleep(60)
        try:
            conn = sqlite3.connect('crypto_bot.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, coin_id, target_price, start_price FROM alerts")
            alerts = cursor.fetchall()
            
            if alerts:
                unique_coins = list(set([a[1] for a in alerts]))
                prices = fetch_prices(unique_coins)
                
                for user_id, coin, target, start in alerts:
                    current = prices.get(coin, {}).get('usd')
                    if not current: continue
                    
                    hit = (target > start and current >= target) or (target < start and current <= target)
                    if hit:
                        emoji = "🚀" if target > start else "📉"
                        await bot.send_message(user_id, f"{emoji} **ЦЕЛЬ ДОСТИГНУТА!**\n{coin.upper()}: `${current:,}`\nТвоя цель была: `${target:,}`", parse_mode="Markdown")
                        cursor.execute("DELETE FROM alerts WHERE user_id=? AND coin_id=? AND target_price=?", (user_id, coin, target))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Alert loop error: {e}")

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Добро пожаловать в CryptoScanner! 🚀\nВыбирай действие в меню:", reply_markup=get_main_kb())

@dp.message(F.text == "🔍 Поиск монеты")
async def search_hint(message: types.Message):
    await message.answer("Просто напиши название монеты (например: `bitcoin`, `solana`, `ethereum`)")

@dp.message(F.text == "📈 Индекс страха")
async def show_fng(message: types.Message):
    try:
        r = requests.get("https://api.alternative.me/fng/").json()
        val = int(r['data'][0]['value'])
        classification = r['data'][0]['value_classification']
        
        desc = "😨 Рынок в страхе. Время покупать?" if val < 40 else "😐 Нейтрально."
        if val > 60: desc = "🤑 Жадность! Будь осторожен."
        
        await message.answer(f"📈 **Индекс страха и жадности:**\n\nЗначение: `{val}/100`\nСтатус: *{classification}*\n\n{desc}", parse_mode="Markdown")
    except:
        await message.answer("Не удалось загрузить индекс.")

@dp.message(F.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT coin_id FROM favorites WHERE user_id = ?', (message.from_user.id,))
    coins = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    if not coins:
        await message.answer("Твой список избранного пуст.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"• {c.upper()}", callback_data=f"view_{c}")] for c in set(coins)
    ])
    await message.answer("⭐ Твои монеты (нажми для управления):", reply_markup=kb)

# Обработка ввода названия монеты
@dp.message()
async def handle_any_text(message: types.Message):
    if message.text.startswith('/'): return
    
    coin_id = message.text.lower().strip().replace(" ", "-")
    data = fetch_prices([coin_id])
    
    if coin_id in data:
        price = data[coin_id]['usd']
        conn = sqlite3.connect('crypto_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM favorites WHERE user_id=? AND coin_id=?', (message.from_user.id, coin_id))
        is_fav = cursor.fetchone() is not None
        conn.close()
        
        await message.answer(
            f"💰 **{coin_id.upper()}**\nЦена: `${price:,}`",
            reply_markup=get_coin_actions_kb(coin_id, is_fav),
            parse_mode="Markdown"
        )
    else:
        await message.answer("Монета не найдена. Проверь ID (например: `bitcoin`, `cardano`)", reply_markup=get_main_kb())

# --- CALLBACKS (Кнопки под сообщениями) ---
@dp.callback_query(F.data.startswith("view_"))
async def view_coin(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    data = fetch_prices([coin_id])
    price = data.get(coin_id, {}).get('usd', '???')
    await callback.message.edit_text(
        f"💰 **{coin_id.upper()}**\nЦена: `${price:,}`",
        reply_markup=get_coin_actions_kb(coin_id, True),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("add_fav_"))
async def add_to_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO favorites VALUES (?, ?)', (callback.from_user.id, coin_id))
    conn.commit()
    conn.close()
    await callback.answer(f"{coin_id} в избранном!")
    await view_coin(callback)

@dp.callback_query(F.data.startswith("rem_fav_"))
async def rem_from_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM favorites WHERE user_id=? AND coin_id=?', (callback.from_user.id, coin_id))
    conn.commit()
    conn.close()
    await callback.answer("Удалено.")
    await callback.message.delete()

@dp.callback_query(F.data.startswith("set_alert_"))
async def alert_prompt(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    data = fetch_prices([coin_id])
    price = data.get(coin_id, {}).get('usd', 0)
    await callback.message.answer(f"Напиши целевую цену для **{coin_id}**.\nСейчас: `${price:,}`\nКоманда: `/set {coin_id} цена` (например: `/set {coin_id} {price*1.1:.2f}`)")
    await callback.answer()

@dp.message(Command("set"))
async def process_alert_command(message: types.Message):
    try:
        parts = message.text.split()
        coin_id = parts[1].lower()
        target = float(parts[2].replace(',', '.'))
        current = fetch_prices([coin_id]).get(coin_id, {}).get('usd')
        
        if current:
            conn = sqlite3.connect('crypto_bot.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO alerts VALUES (?, ?, ?, ?)', (message.from_user.id, coin_id, target, current))
            conn.commit()
            conn.close()
            await message.answer(f"✅ Ок! Слежу за {coin_id}. Цель: `${target:,}`")
        else:
            await message.answer("Ошибка монеты.")
    except:
        await message.answer("Используй: `/set название цена`")

# --- СЕРВЕР ---
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
