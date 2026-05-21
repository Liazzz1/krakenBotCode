import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import os

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    web_app_url = "https://liazzz1.github.io/KrakenUCShop/"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🛒 Открыть магазин",
                web_app=WebAppInfo(url=web_app_url)
            )
        ]
    ])

    await message.answer("Переходите в наше приложение", reply_markup=markup)


@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)

        order_id   = data.get("order_id", "—")
        order_type = data.get("type", "—")
        item       = data.get("item", "—")
        price      = data.get("price", "—")
        status     = data.get("status", "—")

        # Дополнительные поля в зависимости от типа
        extra = ""
        if order_type == "PUBG UC":
            method = data.get("method", "—")
            uid    = data.get("uid")
            extra  = f"🎮 <b>Метод:</b> {method}\n"
            if uid:
                extra += f"🆔 <b>Game ID:</b> <code>{uid}</code>\n"
        elif order_type == "Telegram Stars":
            username = data.get("username", "—")
            extra = f"👤 <b>Username:</b> {username}\n"

        status_emoji = "✅" if status == "paid" else "⏳"

        text = (
            f"🧾 <b>НОВЫЙ ЗАКАЗ</b>\n"
            f"{'─' * 28}\n"
            f"🔑 <b>№ Заказа:</b> <code>{order_id}</code>\n"
            f"📦 <b>Тип:</b> {order_type}\n"
            f"🛍 <b>Товар:</b> {item}\n"
            f"{extra}"
            f"💰 <b>Сумма:</b> {price}\n"
            f"{'─' * 28}\n"
            f"{status_emoji} <b>Статус:</b> Оплачено — ожидает обработки"
        )

        await message.answer(text, parse_mode="HTML")

    except (json.JSONDecodeError, KeyError):
        await message.answer("⚠️ Получены данные в неверном формате.")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
