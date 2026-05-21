import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import os

TOKEN = os.getenv("TOKEN")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

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


@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)

        order_id   = data.get("order_id", "—")
        order_type = data.get("type", "—")
        item       = data.get("item", "—")
        price      = data.get("price", "—")
        status     = data.get("status", "—")

        user = message.from_user
        buyer_info = f"@{user.username}" if user.username else f"id: {user.id}"
        buyer_line = f"👤 <b>Покупатель:</b> {buyer_info} (<code>{user.id}</code>)\n"

        extra = ""
        if order_type == "PUBG UC":
            method = data.get("method", "—")
            uid    = data.get("uid")
            extra  = f"🎮 <b>Метод:</b> {method}\n"
            if uid:
                extra += f"🆔 <b>Game ID:</b> <code>{uid}</code>\n"
        elif order_type == "Telegram Stars":
            username = data.get("username", "—")
            extra = f"📲 <b>TG Username:</b> {username}\n"

        status_emoji = "✅" if status == "paid" else "⏳"

        client_text = (
            f"🧾 <b>ВАШ ЗАКАЗ ПРИНЯТ</b>\n"
            f"{'─' * 28}\n"
            f"🔑 <b>№ Заказа:</b> <code>{order_id}</code>\n"
            f"📦 <b>Тип:</b> {order_type}\n"
            f"🛍 <b>Товар:</b> {item}\n"
            f"{extra}"
            f"💰 <b>Сумма:</b> {price}\n"
            f"{'─' * 28}\n"
            f"{status_emoji} Оплата получена — обрабатываем заказ.\n"
            f"Мы свяжемся с вами в ближайшее время!"
        )

        admin_text = (
            f"🔔 <b>НОВЫЙ ЗАКАЗ</b>\n"
            f"{'─' * 28}\n"
            f"🔑 <b>№ Заказа:</b> <code>{order_id}</code>\n"
            f"📦 <b>Тип:</b> {order_type}\n"
            f"🛍 <b>Товар:</b> {item}\n"
            f"{extra}"
            f"💰 <b>Сумма:</b> {price}\n"
            f"{buyer_line}"
            f"{'─' * 28}\n"
            f"{status_emoji} <b>Статус:</b> Ожидает выполнения"
        )

        await message.answer(client_text, parse_mode="HTML")

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            except Exception as e:
                print(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    except (json.JSONDecodeError, KeyError) as e:
        await message.answer("⚠️ Получены данные в неверном формате.")
        print(f"Ошибка парсинга web_app_data: {e}")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот успешно запущен и готов к работе!")
    if not ADMIN_IDS:
        print("⚠️  ВНИМАНИЕ: переменная ADMIN_IDS не задана — уведомления админу не будут отправляться.")
    else:
        print(f"✅ Уведомления будут отправляться админам: {ADMIN_IDS}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
