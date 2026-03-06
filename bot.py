import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
import config
from database import init_db

# Инициализация бота и диспетчера
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Логика API CoinGecko ---

async def get_coin_price(coin_id: str):
    """Получает цену монеты и изменение за 24 часа по её ID."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id.lower().strip(),
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    
    # Добавляем ключ API, если он указан в конфиге
    headers = {}
    if config.CG_API_KEY:
        headers["x-cg-demo-api-key"] = config.CG_API_KEY

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    # Проверяем, есть ли такая монета в ответе
                    c_id = coin_id.lower().strip()
                    if c_id in data:
                        price = data[c_id]["usd"]
                        change = data[c_id].get("usd_24h_change", 0)
                        return price, change
                return None, None
    except Exception as e:
        print(f"Ошибка при запросе к CoinGecko: {e}")
        return None, None

# --- Клавиатура и команды ---

def get_main_menu():
    kb = [
        [types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")],
        [types.KeyboardButton(text="📊 Индикаторы"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Бот готов к работе! 📊\nЯ могу показывать актуальные курсы криптовалют.\n\n"
        "Введите ID монеты (например: `bitcoin`, `ethereum`, `solana`).",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    await message.answer(
        "Чтобы узнать цену, просто напишите ID монеты латиницей.\n"
        "Примеры: `bitcoin`, `tether`, `dogecoin`, `cardano`.\n\n"
        "P.S. Некоторые монеты могут иметь ID, отличный от их тикера (например, `ripple` вместо `xrp`).",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔍 Найти монету")
async def find_coin_prompt(message: types.Message):
    await message.answer("Введите полное название монеты (ID) на латинице:")

# --- Обработка запросов монет ---

@dp.message()
async def handle_coin_request(message: types.Message):
    if not message.text or message.text.startswith("/"):
        return

    # Игнорируем нажатия на другие кнопки меню, если они не обработаны выше
    if message.text in ["⭐ Избранное", "📊 Индикаторы"]:
        await message.answer(f"Раздел '{message.text}' пока находится в разработке 🛠")
        return

    coin_id = message.text.strip().lower()
    msg_wait = await message.answer(f"🔍 Ищу данные по `{coin_id}`...", parse_mode="Markdown")
    
    price, change = await get_coin_price(coin_id)
    
    if price is not None:
        emoji = "📈" if change >= 0 else "📉"
        # Форматируем цену: если маленькая — больше знаков, если большая — с запятыми
        formatted_price = f"{price:,.2f}" if price >= 1 else f"{price:.6f}"
        
        response_text = (
            f"💰 **{coin_id.upper()}**\n\n"
            f"💵 Цена: `${formatted_price}`\n"
            f"{emoji} Изм. 24ч: `{change:.2f}%`"
        )
        await msg_wait.edit_text(response_text, parse_mode="Markdown")
    else:
        await msg_wait.edit_text(
            f"❌ Монета `{coin_id}` не найдена.\n"
            "Попробуйте уточнить ID на сайте CoinGecko.",
            parse_mode="Markdown"
        )

# --- Настройка Web-сервера для Render ---

async def handle_web(request):
    return web.Response(text="Bot is running")

async def main():
    # 1. Инициализация БД
    await init_db()
    
    # 2. Запуск веб-сервера для Health Check Render
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.PORT)
    await site.start()
    
    print(f"Web server started on port {config.PORT}")
    print("Bot is starting polling...")
    
    # 3. Запуск самого бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
