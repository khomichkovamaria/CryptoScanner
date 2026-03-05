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

# --- API ---
def fetch_prices(coin_ids):
    try:
        clean_ids = [c.strip().lower() for c in coin_ids if c]
        ids_str = ",".join(clean_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd"
        res = requests.get(url, timeout=10).json()
        return res
    except Exception as e:
        logging.error(f"API Error: {e}")
        return {}

# --- МЕНЮ ---
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск монеты"), KeyboardButton(text="⭐ Избранное")],
            [KeyboardButton(text="📈 Индекс страха"), KeyboardButton(text="⚙️ Помощь")]
        ], resize_keyboard=True
    )

def get_coin_control_kb(coin_id, is_fav=False):
    buttons = [
        [InlineKeyboardButton(text="🔔 Добавить алерт", callback_data=f"set_alert_{coin_id}")],
    ]
    if is_fav:
        buttons.append([InlineKeyboardButton(text="❌ Удалить из списка", callback_data=f"rem_fav_{coin_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="⭐ В избранное", callback_data=f"add_fav_{coin_id}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_fav")])
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
            if not alerts: 
                conn.close()
                continue

            unique_coins = list(set([a[1] for a in alerts]))
            prices = fetch_prices(unique_coins)
            
            for user_id, coin, target, start in alerts:
                current = prices.get(coin, {}).get('usd')
                if current is None: continue
                
                if (target > start and current >= target) or (target < start and current <= target):
                    emoji = "🚀" if target > start else "📉"
                    await bot.send_message(user_id, f"{emoji} **ЦЕЛЬ ДОСТИГНУТА!**\n{coin.upper()}: `${current:,}`\nТвоя цель: `${target:,}`", parse_mode="Markdown")
                    cursor.execute("DELETE FROM alerts WHERE user_id=? AND coin_id=? AND target_price=?", (user_id, coin, target))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Loop error: {e}")

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот запущен! 💎 Используй меню для навигации.", reply_markup=get_main_kb())

@dp.message(F.text == "🔍 Поиск монеты")
async def search_msg(message: types.Message):
    await message.answer("Просто отправь мне ID монеты. Примеры:\n`bitcoin`, `ethereum`, `solana`, `dogecoin`", parse_mode="Markdown")

@dp.message(F.text == "📈 Индекс страха")
async def show_fng(message: types.Message):
    try:
        r = requests.get("https://api.alternative.me/fng/").json()
        val = int(r['data'][0]['value'])
        status = r['data'][0]['value_classification']
        advice = "😨 Страх. Хорошее время для покупки?" if val < 30 else "🤑 Жадность. Опасно!"
        if 30 <= val <= 70: advice = "😐 Нейтральное состояние."
        await message.answer(f"📈 **Индекс страха и жадности:**\n\nЗначение: `{val}/100`\nСтатус: *{status}*\n\n{advice}", parse_mode="Markdown")
    except:
        await message.answer("Не удалось загрузить индекс.")

@dp.message(F.text == "⭐ Избранное")
async def list_favs(message: types.Message):
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT coin_id FROM favorites WHERE user_id = ?', (message.from_user.id,))
    coins = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    if not coins:
        await message.answer("Твой список пока пуст. Найди монету и добавь её!")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📊 {c.upper()}", callback_data=f"view_{c}")] for c in coins
    ])
    await message.answer("⭐ Твои монеты:", reply_markup=kb)

# --- УПРАВЛЕНИЕ МОНЕТОЙ ---
async def show_coin_card(chat_id, coin_id, user_id, edit_msg=None):
    data = fetch_prices([coin_id])
    price = data.get(coin_id, {}).get('usd')
    
    if price is None:
        text = f"❌ Монета `{coin_id}` не найдена или API временно недоступен."
        if edit_msg: await edit_msg.edit_text(text, parse_mode="Markdown")
        else: await bot.send_message(chat_id, text, parse_mode="Markdown")
        return

    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM favorites WHERE user_id=? AND coin_id=?', (user_id, coin_id))
    is_fav = cursor.fetchone() is not None
    conn.close()

    text = f"💰 **{coin_id.upper()}**\n\nТекущая цена: `${price:,}`"
    kb = get_coin_control_kb(coin_id, is_fav)
    
    if edit_msg: await edit_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else: await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text)
async def handle_search(message: types.Message):
    if message.text in ["🔍 Поиск монеты", "⭐ Избранное", "📈 Индекс страха", "⚙️ Помощь"]: return
    await show_coin_card(message.chat.id, message.text.lower().strip(), message.from_user.id)

# --- CALLBACKS ---
@dp.callback_query(F.data.startswith("view_"))
async def cb_view(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await show_coin_card(callback.message.chat.id, coin_id, callback.from_user.id, edit_msg=callback.message)
    await callback.answer()

@dp.callback_query(F.data == "back_to_fav")
async def cb_back(callback: types.CallbackQuery):
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT coin_id FROM favorites WHERE user_id = ?', (callback.from_user.id,))
    coins = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"📊 {c.upper()}", callback_data=f"view_{c}")] for c in coins])
    await callback.message.edit_text("⭐ Твои монеты:", reply_markup=kb)

@dp.callback_query(F.data.startswith("add_fav_"))
async def cb_add(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO favorites (user_id, coin_id) VALUES (?, ?)', (callback.from_user.id, coin_id))
    conn.commit()
    conn.close()
    await callback.answer(f"{coin_id.upper()} добавлен в избранное!")
    await cb_view(callback)

@dp.callback_query(F.data.startswith("rem_fav_"))
async def cb_rem(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    conn = sqlite3.connect('crypto_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM favorites WHERE user_id=? AND coin_id=?', (callback.from_user.id, coin_id))
    conn.commit()
    conn.close()
    await callback.answer("Удалено.")
    await cb_back(callback)

@dp.callback_query(F.data.startswith("set_alert_"))
async def cb_alert_prompt(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    price = fetch_prices([coin_id]).get(coin_id, {}).get('usd', 0)
    await callback.message.answer(f"🔔 Установка алерта на **{coin_id.upper()}**\n\nСейчас: `${price:,}`\n\nВведи цену командой:\n`/set {coin_id} {price}`", parse_mode="Markdown")
    await callback.answer()

@dp.message(Command("set"))
async def cmd_set(message: types.Message):
    try:
        parts = message.text.split()
        coin_id, target = parts[1].lower(), float(parts[2].replace(',', '.'))
        current = fetch_prices([coin_id]).get(coin_id, {}).get('usd')
        if current:
            conn = sqlite3.connect('crypto_bot.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO alerts VALUES (?, ?, ?, ?)', (message.from_user.id, coin_id, target, current))
            conn.commit(); conn.close()
            await message.answer(f"✅ Готово! Сообщу, когда {coin_id.upper()} достигнет `${target:,}`")
        else: await message.answer("❌ Ошибка монеты.")
    except: await message.answer("Пример: `/set bitcoin 75000`")

# --- СЕРВЕР ---
async def handle(request): return web.Response(text="OK")
async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(check_alerts_loop())
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
