import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

# --- НАСТРОЙКИ (Берутся из переменных окружения сервера) ---
API_TOKEN = os.getenv('API_TOKEN')
CG_API_KEY = os.getenv('CG_API_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ЛОГИКА КРИПТО-СКАНЕРА ---
def get_crypto_data(coin):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true"
    headers = {"x-cg-demo-api-key": CG_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if coin in data:
            return data[coin]
        return None
    except Exception as e:
        print(f"Ошибка при запросе к API: {e}")
        return None

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Бот запущен на сервере!\nНапиши название монеты (например: bitcoin), и я пришлю курс.")

@dp.message()
async def check_price(message: types.Message):
    coin = message.text.lower().strip()
    data = get_crypto_data(coin)
    
    if data:
        price = data['usd']
        change = data.get('usd_24h_change', 0)
        emoji = "📈" if change > 0 else "📉"
        
        text = (
            f"💰 **Монета:** {coin.capitalize()}\n"
            f"💵 **Цена:** ${price:,}\n"
            f"📊 **Изменение (24ч):** {change:.2f}% {emoji}"
        )
        await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("❌ Монета не найдена. Используй английские названия (например, polkadot).")

# --- КОСТЫЛЬ ДЛЯ ХОСТИНГА (ВЕБ-СЕРВЕР) ---
async def handle(request):
    return web.Response(text="Бот работает!")

async def start_webserver():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render передает порт в переменную окружения PORT
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ЗАПУСК ---
async def main():
    # Запускаем веб-сервер и бота одновременно
    asyncio.create_task(start_webserver())
    print("Бот запущен и готов к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")