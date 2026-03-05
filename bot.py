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
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv('API_TOKEN')
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS alerts 
                          (user_id INTEGER, coin_id TEXT, target_price REAL, start_price REAL)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, coin_id TEXT)')
        conn.commit()

# --- API ФУНКЦИИ (ASYNC) ---
async def fetch_prices(coin_ids):
    try:
        clean_ids = [c.strip().lower() for c in coin_ids if c]
        if not clean_ids: return {}
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(clean_ids)}&vs_currencies=usd"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                return {}
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {}

# --- ФОНОВАЯ ПРОВЕРКА АЛЕРТОВ ---
async def check_alerts():
    while True:
        await asyncio.sleep(60)  # Проверка раз в минуту
        try:
            with sqlite3.connect('crypto_bot.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id, coin_id, target_price, start_price FROM alerts')
                alerts = cursor.fetchall()
                
                if not alerts: continue

                coin_ids = list(set([a[1] for a in alerts]))
                prices = await fetch_prices(coin_ids)
                
                for user_id, coin_id, target, start in alerts:
                    current = prices.get(coin_id, {}).get('usd')
                    if current is None: continue
                    
                    # Проверка пересечения цены
                    if (start <= target <= current) or (start >= target >= current):
                        try:
                            await bot.send_message(
                                user_id, 
                                f"🔔 **УВЕДОМЛЕНИЕ!**\n{coin_id.upper()} достиг цели: `${current:,.2f}`\n(Таргет: ${target:,.2f})"
                            )
                            cursor.execute('DELETE FROM alerts WHERE user_id=? AND coin_id=? AND target_price=?', 
                                         (user_id, coin_id, target))
                        except Exception as e:
                            logger.error(f"Failed to send alert to {user_id}: {e}")
                conn.commit()
        except Exception as e:
            logger.error(f"Alert Loop Error: {e}")

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Поиск монеты"), KeyboardButton(text="⭐ Избранное")],
            [KeyboardButton(text="📈 Индекс страха"), KeyboardButton(text="⚙️ Помощь")]
        ], resize_keyboard=True
    )

def get_coin_menu(coin_id, is_fav=False):
    fav_text = "❌ Удалить из избранного" if is_fav else "⭐ В избранное"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Поставить алерт", callback_data=f"setup_alert_{coin_id}")],
        [InlineKeyboardButton(text=fav_text, callback_data=f"toggle_fav_{coin_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
    ])

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🚀 Бот запущен и готов к работе!", reply_markup=get_main_kb())

@dp.message(Command("set"))
async def set_alert(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: `/set bitcoin 65000`", parse_mode="Markdown")
    try:
        parts = command.args.split()
        coin_id = parts[0].lower()
        target_price = float(parts[1].replace(',', '.'))
        
        data = await fetch_prices([coin_id])
        current_price = data.get(coin_id, {}).get('usd')
        
        if current_price is None:
            return await message.answer("❌ Монета не найдена.")

        with sqlite3.connect('crypto_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO alerts VALUES (?, ?, ?, ?)', 
                         (message.from_user.id, coin_id, target_price, current_price))
            conn.commit()
        await message.answer(f"✅ Алерт на {coin_id.upper()} создан! (Цель: ${target_price:,.2f})")
    except:
        await message.answer("❌ Ошибка. Используйте формат: `/set bitcoin 50000`")

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

@dp.message(F.text == "📈 Индекс страха")
async def fng_msg(message: types.Message):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.alternative.me/fng/") as r:
            data = await r.json()
            val = data['data'][0]['value']
            status = data['data'][0]['value_classification']
            await message.answer(f"📈 Индекс страха и жадности: `{val}/100` ({status})", parse_mode="Markdown")

@dp.message(F.text == "⚙️ Помощь")
async def help_cmd(message: types.Message):
    text = (
        "📖 **Справка:**\n\n"
        "• Отправьте название (ID) монеты для поиска (напр. `ethereum`)\n"
        "• `/set ID цена` — поставить уведомление\n"
        "• Кнопка ⭐ — быстрый доступ к монетам"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text)
async def coin_search(message: types.Message):
    if message.text.startswith(("/", "🔍", "⭐", "📈", "⚙️")): return
    
    coin_id = message.text.lower().strip()
    data = await fetch_prices([coin_id])
    price = data.get(coin_id, {}).get('usd')

    if price is None:
        return await message.answer(f"❌ Монета `{coin_id}` не найдена.")

    with sqlite3.connect('crypto_bot.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM favorites WHERE user_id=? AND coin_id=?', (message.from_user.id, coin_id))
        is_fav = cursor.fetchone() is not None

    await message.answer(
        f"💰 **{coin_id.upper()}**\nТекущая цена: `${price:,.2f}`",
        reply_markup=get_coin_menu(coin_id, is_fav),
        parse_mode="Markdown"
    )

# --- CALLBACKS ---
@dp.callback_query(F.data.startswith("view_"))
async def cb_view(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    data = await fetch_prices([coin_id])
    price = data.get(coin_id, {}).get('usd')
    
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
            msg = "Удалено"
        else:
            cursor.execute('INSERT INTO favorites VALUES (?, ?)', (callback.from_user.id, coin_id))
            msg = "Добавлено"
        conn.commit()
    await callback.answer(msg)
    await cb_view(callback)

@dp.callback_query(F.data == "setup_alert_")
async def cb_setup_alert_hint(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[2]
    await callback.message.answer(f"Чтобы поставить алерт, введите команду:\n`/set {coin_id} цена`", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_to_list")
async def cb_back(callback: types.CallbackQuery):
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

# --- WEB SERVER ---
async def handle(request): return web.Response(text="Bot is alive!")

# --- ЗАПУСК ---
async def main():
    init_db()
    
    # Запуск веб-сервера
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    
    # Фоновая проверка алертов
    asyncio.create_task(check_alerts())
    
    # Решение конфликта (Conflict Error)
    # Удаляем вебхук и ждем 3 секунды, чтобы Render закрыл старую копию
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(3)
    
    logger.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
