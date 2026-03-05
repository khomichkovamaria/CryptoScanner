import os
import asyncio
import sqlite3
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# Настройка логов
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('API_TOKEN')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        # Добавили current_price, чтобы понимать, в какую сторону шел тренд при установке
        cursor.execute('''CREATE TABLE IF NOT EXISTS alerts 
                          (user_id INTEGER, coin_id TEXT, target_price REAL, start_price REAL)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, coin_id TEXT)')
        conn.commit()

# --- API ФУНКЦИИ ---
async def fetch_prices(coin_ids):
    try:
        clean_ids = [c.strip().lower() for c in coin_ids if c]
        if not clean_ids: return {}
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(clean_ids)}&vs_currencies=usd"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                return await response.json()
    except Exception as e:
        logging.error(f"API Error: {e}")
        return {}

# --- ФОНОВАЯ ПРОВЕРКА АЛЕРТОВ ---
async def check_alerts():
    while True:
        try:
            with sqlite3.connect('crypto_bot.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id, coin_id, target_price, start_price FROM alerts')
                alerts = cursor.fetchall()
                
                if alerts:
                    coin_ids = list(set([a[1] for a in alerts]))
                    prices = await fetch_prices(coin_ids)
                    
                    for user_id, coin_id, target, start in alerts:
                        current = prices.get(coin_id, {}).get('usd')
                        if not current: continue
                        
                        # Логика: если цена пересекла таргет (сверху вниз или снизу вверх)
                        if (start <= target <= current) or (start >= target >= current):
                            await bot.send_message(user_id, f"🔔 **ALERT!**\n{coin_id.upper()} достиг цены `${current:,.2f}`!")
                            cursor.execute('DELETE FROM alerts WHERE user_id=? AND coin_id=? AND target_price=?', 
                                         (user_id, coin_id, target))
                conn.commit()
        except Exception as e:
            logging.error(f"Alert check error: {e}")
        
        await asyncio.sleep(60) # Проверка раз в минуту

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск монеты"), KeyboardButton(text="⭐ Избранное")],
            [KeyboardButton(text="📈 Индекс страха"), KeyboardButton(text="⚙️ Помощь")]
        ], resize_keyboard=True
    )

def get_coin_menu(coin_id, is_fav=False):
    buttons = [
        [InlineKeyboardButton(text="🔔 Добавить алерт", callback_data=f"setup_alert_{coin_id}")],
        [InlineKeyboardButton(text="❌ Удалить из избранного" if is_fav else "⭐ В избранное", 
                              callback_data=f"toggle_fav_{coin_id}")]
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    init_db()
    await message.answer("🚀 Бот готов к мониторингу!", reply_markup=get_main_kb())

@dp.message(Command("set"))
async def set_alert_command(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Используй: `/set bitcoin 65000`", parse_mode="Markdown")
    
    try:
        coin_id, target_price = command.args.split()
        target_price = float(target_price.replace(',', '.'))
        
        data = await fetch_prices([coin_id])
        current_price = data.get(coin_id.lower(), {}).get('usd')
        
        if current_price is None:
            return await message.answer("❌ Монета не найдена")

        with sqlite3.connect('crypto_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO alerts VALUES (?, ?, ?, ?)', 
                         (message.from_user.id, coin_id.lower(), target_price, current_price))
            conn.commit()
            
        await message.answer(f"✅ Алерт установлен! Уведомлю, когда {coin_id} достигнет ${target_price:,.2f}")
    except ValueError:
        await message.answer("Ошибка! Формат: `/set bitcoin 65000`")

@dp.message(F.text == "⭐ Избранное")
async def favorites_list(message: types.Message):
    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT coin_id FROM favorites WHERE user_id = ?', (message.from_user.id,))
        coins = [r[0] for r in cursor.fetchall()]
    
    if not coins:
        return await message.answer("Ваш список избранного пуст.")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📊 {c.upper()}", callback_data=f"view_{c}")] for c in coins
    ])
    await message.answer("⭐ Ваше избранное:", reply_markup=kb)

@dp.message(F.text == "🔍 Поиск монеты")
async def search_help(message: types.Message):
    await message.answer("Просто отправьте ID монеты (например, `ethereum` или `solana`)")

@dp.message(F.text)
async def coin_search(message: types.Message):
    if message.text in ["🔍 Поиск монеты", "⭐ Избранное", "📈 Индекс страха", "⚙️ Помощь"]: return

    coin_id = message.text.lower().strip()
    price_data = await fetch_prices([coin_id])
    price = price_data.get(coin_id, {}).get('usd')

    if price is None:
        return await message.answer(f"❌ Монета `{coin_id}` не найдена.")

    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM favorites WHERE user_id=? AND coin_id=?', (message.from_user.id, coin_id))
        is_fav = cursor.fetchone() is not None

    await message.answer(
        f"💰 **{coin_id.upper()}**\nЦена: `${price:,.2f}`",
        reply_markup=get_coin_menu(coin_id, is_fav),
        parse_mode="Markdown"
    )

# --- CALLBACKS ---
@dp.callback_query(F.data.startswith("view_"))
async def cb_view(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    price_data = await fetch_prices([coin_id])
    price = price_data.get(coin_id, {}).get('usd')
    
    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM favorites WHERE user_id=? AND coin_id=?', (callback.from_user.id, coin_id))
        is_fav = cursor.fetchone() is not None

    await callback.message.edit_text(
        f"💰 **{coin_id.upper()}**\nЦена: `${price:,.2f}`",
        reply_markup=get_coin_menu(coin_id, is_fav),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("toggle_fav_"))
async def cb_toggle_fav(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM favorites WHERE user_id=? AND coin_id=?', (callback.from_user.id, coin_id))
        if cursor.fetchone():
            cursor.execute('DELETE FROM favorites WHERE user_id=? AND coin_id=?', (callback.from_user.id, coin_id))
            res = "Удалено"
        else:
            cursor.execute('INSERT INTO favorites VALUES (?, ?)', (callback.from_user.id, coin_id))
            res = "Добавлено"
        conn.commit()
    
    await callback.answer(res)
    # Обновляем карточку
    await cb_view(callback)

@dp.callback_query(F.data == "back_to_list")
async def cb_back(callback: types.CallbackQuery):
    # Вместо отправки нового сообщения, редактируем старое
    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT coin_id FROM favorites WHERE user_id = ?', (callback.from_user.id,))
        coins = [r[0] for r in cursor.fetchall()]
    
    if not coins:
        return await callback.message.edit_text("Список пуст.", reply_markup=None)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📊 {c.upper()}", callback_data=f"view_{c}")] for c in coins
    ])
    await callback.message.edit_text("⭐ Твои монеты:", reply_markup=kb)

# --- WEB SERVER & START ---
async def handle(request): return web.Response(text="OK")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080))).start()
    
    # Запускаем фоновую задачу для алертов
    asyncio.create_task(check_alerts())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
