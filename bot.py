import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# --- НАСТРОЙКИ (Берутся из Environment Variables на Render) ---
API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ФУНКЦИЯ СОЗДАНИЯ КНОПОК ---
def get_main_keyboard():
    # Создаем кнопки
    btn_btc = KeyboardButton(text="BTC 🟠")
    btn_eth = KeyboardButton(text="ETH 🔵")
    btn_sol = KeyboardButton(text="SOL 🟣")
    btn_ton = KeyboardButton(text="TON 💎")
    btn_index = KeyboardButton(text="📈 Индекс Страха/Жадности")
    btn_help = KeyboardButton(text="❓ Помощь")

    # Группируем их в ряды
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [btn_btc, btn_eth],
            [btn_sol, btn_ton],
            [btn_index, btn_help]
        ],
        resize_keyboard=True # Делает кнопки аккуратными по размеру
    )
    return keyboard

# --- ЛОГИКА ПОЛУЧЕНИЯ ДАННЫХ (CoinGecko) ---
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

# --- ОБРАБОТЧИК КОМАНДЫ /START ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой обновленный крипто-помощник.\n\n"
        "Теперь тебе не нужно печатать названия — просто нажимай на кнопки ниже!",
        reply_markup=get_main_keyboard()
    )

# --- ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ И КНОПОК ---
@dp.message()
async def handle_all_messages(message: types.Message):
    text = message.text.lower()
    
    # Карта соответствия текста на кнопке и ID в системе CoinGecko
    coins_map = {
        "btc 🟠": "bitcoin",
        "eth 🔵": "ethereum",
        "sol 🟣": "solana",
        "ton 💎": "the-open-network"
    }

    # 1. Если нажата кнопка с монетой
    if text in coins_map:
        coin_id = coins_map[text]
        data = get_crypto_data(coin_id)
        if data:
            price = data['usd']
            change = data.get('usd_24h_change', 0)
            emoji = "🚀" if change > 0 else "🔻"
            await message.answer(
                f"💰 **{text.upper()}**\n"
                f"Цена: `${price:,}`\n"
                f"Изменение за 24ч: `{change:.2f}%` {emoji}",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
    
    # 2. Если нажата кнопка "Индекс"
    elif "индекс" in text:
        await message.answer(
            "📊 **Индекс Страха и Жадности**\n\n"
            "Пока в разработке... Но скоро я буду присылать аналитику настроения рынка!",
            reply_markup=get_main_keyboard()
        )
    
    # 3. Если нажата кнопка "Помощь"
    elif "помощь" in text:
        await message.answer(
            "Просто жми на кнопки популярных монет.\n\n"
            "Если нужной монеты нет в меню, напиши её название на английском (например: `dogecoin`).",
            reply_markup=get_main_keyboard()
        )
    
    # 4. Если пользователь ввел название монеты вручную
    else:
        data = get_crypto_data(text)
        if data:
            price = data['usd']
            change = data.get('usd_24h_change', 0)
            await message.answer(
                f"✅ Нашел монету: **{text.capitalize()}**\n"
                f"Цена: `${price:,}`\n"
                f"Изменение: `{change:.2f}%`",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                "🤔 Не узнаю такую монету. Попробуй выбрать из меню или проверь написание.",
                reply_markup=get_main_keyboard()
            )

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (Чтобы бот не засыпал) ---
async def handle(request):
    return web.Response(text="Бот работает и кнопки активны!")

async def start_webserver():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ГЛАВНЫЙ ЗАПУСК ---
async def main():
    # Запускаем веб-сервер фоном
    asyncio.create_task(start_webserver())
    # Запускаем чтение сообщений
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
