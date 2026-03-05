import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Хранилище для уведомлений (в памяти)
alerts = {} 

# --- КЛАВИАТУРА ---
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC 🟠"), KeyboardButton(text="ETH 🔵")],
            [KeyboardButton(text="📈 Индекс Страха/Жадности"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

# --- ПОЛУЧЕНИЕ ЦЕН ---
def get_crypto_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    headers = {"x-cg-demo-api-key": CG_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json().get(coin_id)
    except: return None

# --- ФОНОВАЯ ПРОВЕРКА ЦЕНЫ ---
async def check_alerts():
    while True:
        await asyncio.sleep(60) # Проверяем раз в минуту
        if not alerts: continue
        
        data = get_crypto_data("bitcoin")
        if data:
            current_price = data['usd']
            for user_id, target_price in list(alerts.items()):
                if current_price <= target_price:
                    await bot.send_message(user_id, f"🔔 **ALERT!**\nBitcoin упал до `${current_price:,}`\nТвоя цель `${target_price:,}` достигнута! 🚀")
                    del alerts[user_id] # Удаляем, чтобы не спамить

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Я слежу за рынком. Чтобы поставить уведомление на BTC, напиши:\n`/alert 90000`", parse_mode="Markdown", reply_markup=get_main_keyboard())

@dp.message(Command("alert"))
async def set_alert(message: types.Message):
    try:
        price = int(message.text.split()[1])
        alerts[message.from_user.id] = price
        await message.answer(f"✅ Ок! Я напишу тебе, когда Bitcoin упадет до ${price:,}")
    except:
        await message.answer("Ошибка! Напиши команду вот так: `/alert 90000` (только число)")

@dp.message()
async def handle_all(message: types.Message):
    text = message.text.lower()
    if "btc" in text:
        data = get_crypto_data("bitcoin")
        if data: await message.answer(f"BTC: `${data['usd']:,}`", parse_mode="Markdown")
    elif "индекс" in text:
        # (Тут остается твоя функция индекса из прошлого шага)
        await message.answer("Индекс работает! (код сокращен для краткости)")

# --- ВЕБ-СЕРВЕР И ЗАПУСК ---
async def handle(request): return web.Response(text="OK")

async def main():
    asyncio.create_task(check_alerts()) # Запускаем "слежку" в фоне
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
