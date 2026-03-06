import asyncio
import os
from aiogram import Bot, Dispatcher
from aiohttp import web

# Импортируем наши модули
import config
from database import init_db
from handlers import common

# Инициализация бота и диспетчера
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# Регистрация роутеров (наших обработчиков)
dp.include_router(common.router)

# --- ВЕБ-СЕРВЕР ДЛЯ HEALTH CHECK (Нужен для Render) ---
async def handle(request):
    return web.Response(text="Bot is running")

async def main():
    # 1. Запускаем базу данных (создаем таблицы)
    await init_db()
    
    # 2. Запускаем веб-сервер на фоне
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.PORT)
    await site.start()
    
    # 3. Запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
