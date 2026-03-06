import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
import config
import database
import api_service

bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()

def get_main_menu():
    kb = [[types.KeyboardButton(text="🔍 Найти монету"), types.KeyboardButton(text="⭐ Избранное")], [types.KeyboardButton(text="❓ Помощь")]]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот-аналитик ожил! 🚀", reply_markup=get_main_menu())

async def send_coin_card(message: types.Message, coin_query: str, edit_message=None):
    data = await api_service.get_coin_data(coin_query)
    if data:
        coin_id = data['id']
        is_fav = await database.is_favorite(message.chat.id, coin_id)
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🗑 Удалить" if is_fav else "⭐ В избранное", callback_data=f"{'rem' if is_fav else 'fav'}_{coin_id}_{data['ticker']}"))
        builder.row(types.InlineKeyboardButton(text="📊 Тех. анализ (RSI)", callback_data=f"tf_{coin_id}"))
        
        res = f"💰 **{data['ticker']}**\n\n💵 Цена: `${data['price']:,.2f}`\n{'📈' if data['change']>=0 else '📉'} 24ч: `{data['change']:.2f}%`"
        if edit_message: await edit_message.edit_text(res, parse_mode="Markdown", reply_markup=builder.as_markup())
        else: await message.answer(res, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        err = f"❌ Монета `{coin_query}` не найдена на биржах."
        if edit_message: await edit_message.edit_text(err, parse_mode="Markdown")
        else: await message.answer(err, parse_mode="Markdown")

@dp.message(F.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    favs = await database.get_favorites(message.from_user.id)
    if not favs: return await message.answer("Ваш список избранного пуст.")
    builder = InlineKeyboardBuilder()
    for item in favs:
        builder.add(types.InlineKeyboardButton(text=item['ticker'], callback_data=f"price_{item['coin_id']}"))
    builder.adjust(3)
    await message.answer("⭐ Ваше избранное:", reply_markup=builder.as_markup())

@dp.message()
async def handle_all(message: types.Message):
    if message.text in ["🔍 Найти монету", "❓ Помощь"]:
        await message.answer("Просто введите название или тикер монеты (напр. BTC или Bitcoin)")
        return
    msg = await message.answer("📡 Связываюсь с биржей...")
    await send_coin_card(message, message.text, edit_message=msg)

@dp.callback_query(F.data.startswith("tf_"))
async def show_analysis(callback: types.CallbackQuery):
    coin_id = callback.data.split("_")[1]
    await callback.answer("📊 Считаю...")
    analysis = await api_service.get_multi_rsi(coin_id)
    await callback.message.answer(f"📊 **Анализ {coin_id.upper()}:**\n\n{analysis}", parse_mode="Markdown")

@dp.callback_query(F.data.contains("fav_") or F.data.contains("rem_"))
async def handle_fav(callback: types.CallbackQuery):
    action, coin_id, ticker = callback.data.split("_")
    if action == "fav": await database.add_favorite(callback.from_user.id, coin_id, ticker)
    else: await database.remove_favorite(callback.from_user.id, coin_id)
    await callback.answer("Обновлено")
    await send_coin_card(callback.message, coin_id, edit_message=callback.message)

@dp.callback_query(F.data.startswith("price_"))
async def price_call(callback: types.CallbackQuery):
    await callback.answer()
    await send_coin_card(callback.message, callback.data.split("_")[1])

async def main():
    await database.init_db()
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', config.PORT).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
