import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiohttp import web
import config
from database import init_db

# Инициализация
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# Главное меню
def get_main_menu():
    kb = [
        [types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")],
        [types.KeyboardButton(text="📊 Индикаторы"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот обновлен! 🚀\nИспользуйте меню ниже:", reply_markup=get_main_menu())

@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    await message.answer("Введите название монеты (например, bitcoin или ethereum), чтобы получить текущий курс.")

@dp.message(F.text == "🔍 Найти монету")
async def find_coin_start(message: types.Message):
    await message.answer("Напишите название монеты латиницей (например: bitcoin)")

# Простейший поиск (пока без API, просто проверка связи)
@dp.message()
async def handle_any_text(message: types.Message):
    if message.text:
        await message.answer(f"Ищу информацию по запросу: {message.text}...\n(На следующем шаге я подключу сюда реальные цены Coingecko!)")

# Настройка Web-сервера для Render
async def handle_web(request):
    return web.Response(text="Bot is running")

async def main():
    await init_db()
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.PORT)
    await site.start()
    
    print("Bot is starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
