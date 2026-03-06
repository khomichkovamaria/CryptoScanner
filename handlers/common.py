from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards.reply import get_main_kb

# Роутер — это как распределитель команд внутри папки
router = Router()

@router.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "Бот обновлен! 🚀\nИспользуйте меню ниже:", 
        reply_markup=get_main_kb()
    )

@router.message(F.text == "📱 Меню")
async def back_to_menu(message: types.Message, state: FSMContext):
    await state.clear() # Сбрасываем все ожидания ввода от пользователя
    await message.answer("Главное меню", reply_markup=get_main_kb())

@router.message(F.text == "❓ Помощь")
async def help_cmd(message: types.Message):
    await message.answer("Раздел помощи: используйте кнопки для навигации по курсам валют.")
