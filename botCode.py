import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Укажите здесь токен вашего бота, полученный у @BotFather
TOKEN = "8601701792:AAFt5mgc4eyxYya1_xSzmDWWi2FJ621JyI0"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем кнопку для открытия Web App
    # Замените URL на ссылку на ваше приложение
    web_app_url = "https://liazzz1.github.io/KrakenUCShop/"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Открыть приложение", 
                web_app=WebAppInfo(url=web_app_url)
            )
        ]
    ])
    
    await message.answer("Переходите в наше приложение", reply_markup=markup)

async def main():
    # Удаляем вебхук перед запуском поллинга
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())