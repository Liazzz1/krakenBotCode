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
        [InlineKeyboardButton(text="🛒 Открыть магазин", web_app=WebAppInfo(url=web_app_url))]
    ])
    await message.answer("Переходите в наше приложение", reply_markup=markup)


@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


# Логируем ВСЕ входящие сообщения — чтобы видеть доходит ли что-то от мини-аппа
@dp.message()
async def log_all(message: types.Message):
    print(f"📨 Сообщение от {message.from_user.id}: content_type={message.content_type}")
    if message.web_app_data:
        print(f"✅ web_app_data ПОЛУЧЕНЫ: {message.web_app_data.data}")
        await handle_order(message)
    else:
        print(f"⚠️ Это не web_app_data. Текст: {message.text}")


@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    print(f"✅ [F.web_app_data] сработал от {message.from_user.id}")
    await handle_order(message)


async def handle_order(message: types.Message):
    try:
        raw = message.web_app_data.data
        print(f"📦 RAW данные: {raw}")
        data = json.loads(raw)

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
        print(f"✅ Подтверждение отправлено клиенту {user.id}")

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
                print(f"✅ Уведомление отправлено админу {admin_id}")
            except Exception as e:
                print(f"❌ Не удалось отправить админу {admin_id}: {e}")

    except Exception as e:
        print(f"❌ Ошибка обработки заказа: {e}")
        await message.answer("⚠️ Получены данные в неверном формате.")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Бот запущен!")
    if not ADMIN_IDS:
        print("⚠️ ADMIN_IDS не задан!")
    else:
        print(f"✅ Уведомления будут отправляться админам: {ADMIN_IDS}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
