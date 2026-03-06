import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
import config
from database import init_db, add_favorite, get_favorites

# Инициализация
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

# --- Логика API CoinGecko ---

async def get_coin_price(coin_id: str):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id.lower().strip(),
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    headers = {"x-cg-demo-api-key": config.CG_API_KEY} if config.CG_API_KEY else {}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    c_id = coin_id.lower().strip()
                    if c_id in data:
                        return data[c_id]["usd"], data[c_id].get("usd_24h_change", 0)
                return None, None
    except Exception as e:
        print(f"Ошибка API: {e}")
        return None, None

# --- Клавиатуры ---

def get_main_menu():
    kb = [
        [types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")],
        [types.KeyboardButton(text="📊 Индикаторы"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- Команды ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Бот запущен! 📊\nНапишите ID монеты (например: `bitcoin`) или используйте меню:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔍 Найти монету")
async def find_coin_prompt(message: types.Message):
    await message.answer("Введите ID монеты латиницей (например: `solana`, `polkadot`):", parse_mode="Markdown")

@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    await message.answer("Просто введите ID монеты с CoinGecko. Пример: `dogecoin`, `ripple`, `ethereum`.")

# --- Логика "Избранного" ---

@dp.message(F.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    favs = await get_favorites(message.from_user.id)
    if not favs:
        await message.answer("Ваш список избранного пока пуст. Добавьте монеты через поиск!")
        return
    
    text = "⭐ **Ваше избранное:**\n\n" + "\n".join([f"• `{f.capitalize()}`" for f in favs])
    text += "\n\nЧтобы узнать свежую цену, просто нажмите на название (если настроите ссылки) или введите его вручную."
    await message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("fav_"))
async def process_add_favorite(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    # Записываем в базу данных
    await add_favorite(user_id, coin_id)
    
    # Убираем "часики" с кнопки и показываем уведомление
    await callback.answer(f"✅ {coin_id.capitalize()} добавлен в избранное!")
    # Можно обновить текст, чтобы кнопка исчезла или изменилась
    await callback.message.edit_reply_markup(reply_markup=None)

# --- Основной обработчик монет ---

@dp.message()
async def handle_coin_request(message: types.Message):
    if not message.text or message.text.startswith("/") or message.text in ["📊 Индикаторы"]:
        return

    coin_id = message.text.strip().lower()
    msg_wait = await message.answer(f"🔍 Ищу данные по `{coin_id}`...", parse_mode="Markdown")
    
    price, change = await get_coin_price(coin_id)
    
    if price is not None:
        emoji = "📈" if change >= 0 else "📉"
        formatted_price = f"{price:,.2f}" if price >= 1 else f"{price:.6f}"
        
        # Создаем кнопку под ценой
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="⭐ В избранное", 
            callback_data=f"fav_{coin_id}")
        )

        response_text = (
            f"💰 **{coin_id.upper()}**\n\n"
            f"💵 Цена: `${formatted_price}`\n"
            f"{emoji} Изм. 24ч: `{change:.2f}%`"
        )
        await msg_wait.edit_text(response_text, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        await msg_wait.edit_text(f"❌ Монета `{coin_id}` не найдена.")

# --- Настройка Web-сервера для Render ---

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
    
    print(f"Server started on port {config.PORT}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
