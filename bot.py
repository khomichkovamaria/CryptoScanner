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
    buttons = [
        [KeyboardButton(text="BTC 🟠"), KeyboardButton(text="ETH 🔵")],
        [KeyboardButton(text="SOL 🟣"), KeyboardButton(text="TON 💎")],
        [KeyboardButton(text="📈 Индекс Страха/Жадности"), KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ЛОГИКА API ---
def get_crypto_data(coin_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
    headers = {"x-cg-demo-api-key": CG_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if coin_id in data:
            return data[coin_id]
        return None
    except Exception as e:
        print(f"Ошибка API: {e}")
        return None

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой крипто-помощник.\nВыбирай монету из меню ниже или напиши название сам.",
        reply_markup=get_main_keyboard()
    )

@dp.message()
async def handle_message(message: types.Message):
    text = message.text.lower()
    
    # Словарик для кнопок (чтобы сопоставить текст кнопки с ID в CoinGecko)
    coins_map = {
        "btc 🟠": "bitcoin",
        "eth 🔵": "ethereum",
        "sol 🟣": "solana",
        "ton 💎": "the-open-network"
    }

    if text in coins_map:
        coin_id = coins_map[text]
        data = get_crypto_data(coin_id)
        if data:
            price = data['usd']
            change = data.get('usd_24h_change', 0)
            emoji = "📈" if change > 0 else "📉"
            await message.answer(f"💰 **{text.upper()}**\nЦена: ${price:,}\nИзменение: {change:.2f}% {emoji}", parse_mode="Markdown")
    
    elif "помощь" in text:
        await message.answer("Просто нажимай на кнопки или напиши название монеты на английском (например, 'dogecoin').")
    
    elif "индекс" in text:
        await message.answer("⏳ Функция аналитики 'Индекс Страха' будет добавлена в следующем обновлении!")
    
    else:
        # Если пользователь ввел что-то свое
        data = get_crypto_data(text)
        if data:
            await message.answer(f"✅ Нашел: {text.capitalize()}\nЦена: ${data['usd']}\nИзменение: {data.get('usd_24h_change', 0):.2f}%")
        else:
            await message.answer("🤔 Не узнаю монету. Попробуй выбрать из меню.")

# --- ВЕБ-СЕРВЕР (Для Render) ---
async def handle(request):
    return web.Response(text="Бот работает!")

async def start_webserver():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    asyncio.create_task(start_webserver())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
