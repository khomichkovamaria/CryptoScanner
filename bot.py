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

# --- КЛАВИАТУРА ---
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC 🟠"), KeyboardButton(text="ETH 🔵")],
            [KeyboardButton(text="SOL 🟣"), KeyboardButton(text="TON 💎")],
            [KeyboardButton(text="📈 Индекс Страха/Жадности"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

# --- ПОЛУЧЕНИЕ ЦЕН (CoinGecko) ---
def get_crypto_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
    headers = {"x-cg-demo-api-key": CG_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json().get(coin_id)
    except: return None

# --- НОВАЯ ФУНКЦИЯ: ИНДЕКС СТРАХА И ЖАДНОСТИ ---
def get_fear_greed_index():
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=10)
        data = response.json()
        value = int(data['data'][0]['value'])
        status = data['data'][0]['value_classification']
        
        # Переводим статус на русский для красоты
        translate = {
            "Extreme Fear": "Экстремальный страх 😱 (Покупай!)",
            "Fear": "Страх 😨",
            "Neutral": "Нейтрально 😐",
            "Greed": "Жадность 🤑",
            "Extreme Greed": "Экстремальная жадность 🤩 (Опасно!)"
        }
        status_ru = translate.get(status, status)
        return f"📊 **Индекс страха и жадности: {value}/100**\nСтатус: {status_ru}"
    except:
        return "❌ Не удалось получить данные индекса."

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Выбирай инструмент в меню:", reply_markup=get_main_keyboard())

@dp.message()
async def handle_all(message: types.Message):
    text = message.text.lower()
    
    # Кнопки монет
    coins = {"btc 🟠": "bitcoin", "eth 🔵": "ethereum", "sol 🟣": "solana", "ton 💎": "the-open-network"}
    
    if text in coins:
        data = get_crypto_data(coins[text])
        if data:
            price, change = data['usd'], data.get('usd_24h_change', 0)
            await message.answer(f"💰 **{text.upper()}**\nЦена: `${price:,}`\n24ч: `{change:.2f}%`", parse_mode="Markdown")
    
    # Кнопка Индекса
    elif "индекс" in text:
        info = get_fear_greed_index()
        await message.answer(info, parse_mode="Markdown")
    
    elif "помощь" in text:
        await message.answer("Жми кнопки или пиши имя монеты на англ.")
    
    else:
        # Ручной ввод
        data = get_crypto_data(text)
        if data:
            await message.answer(f"✅ {text.capitalize()}: `${data['usd']}`")
        else:
            await message.answer("Не понимаю. Используй кнопки.")

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request): return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
