import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import os

TOKEN     = os.getenv("TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

bot = Bot(token=TOKEN)
dp  = Dispatcher()

# user_id -> order_id
pending_receipts: dict[int, str] = {}


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🛒 Открыть магазин",
            web_app=WebAppInfo(url="https://liazzz1.github.io/KrakenUCShop/")
        )
    ]])
    await message.answer("Переходите в наше приложение", reply_markup=markup)


@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>",
        parse_mode="HTML"
    )


# ── Служебное сообщение от фронтенда ─────────────────────────────────────────
# Фронтенд шлёт __NOTIFY_CLIENT__:CLIENT_ID:ORDER_ID боту в личку клиента.
# Бот получает это сообщение, сохраняет pending и просит квитанцию.
@dp.message(F.text.startswith("__NOTIFY_CLIENT__:"))
async def handle_notify_client(message: types.Message):
    try:
        parts = message.text.split(":", 2)
        client_id = int(parts[1])
        order_id  = parts[2]
    except Exception as e:
        print(f"❌ Ошибка парсинга NOTIFY_CLIENT: {e}")
        try:
            await message.delete()
        except:
            pass
        return

    # Сохраняем pending
    pending_receipts[client_id] = order_id
    print(f"✅ Pending: client={client_id} order={order_id}")

    # Просим квитанцию у клиента
    try:
        await bot.send_message(
            client_id,
            f"📎 Для подтверждения заказа <b>№{order_id}</b>\n\n"
            f"Отправьте <b>скриншот или фото квитанции об оплате</b> прямо сюда.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"❌ Не удалось написать клиенту {client_id}: {e}")

    # Удаляем служебное сообщение из чата
    try:
        await message.delete()
    except Exception:
        pass


# ── Фото или документ — квитанция ────────────────────────────────────────────
@dp.message(F.photo | F.document)
async def handle_receipt(message: types.Message):
    user    = message.from_user
    user_id = user.id

    order_id = pending_receipts.get(user_id)
    if not order_id:
        await message.answer(
            "⚠️ Квитанция не принята.\n\n"
            "Сначала оформите заказ в магазине — после оплаты "
            "бот сам попросит вас прислать квитанцию."
        )
        return

    del pending_receipts[user_id]

    buyer_info    = f"@{user.username}" if user.username else f"id: {user_id}"
    admin_caption = (
        f"🧾 <b>КВИТАНЦИЯ ОБ ОПЛАТЕ</b>\n"
        f"{'─' * 28}\n"
        f"🔑 <b>№ Заказа:</b> <code>{order_id}</code>\n"
        f"👤 <b>От:</b> {buyer_info} (<code>{user_id}</code>)"
    )

    sent = False
    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(
                    admin_id,
                    photo=message.photo[-1].file_id,
                    caption=admin_caption,
                    parse_mode="HTML"
                )
            else:
                await bot.send_document(
                    admin_id,
                    document=message.document.file_id,
                    caption=admin_caption,
                    parse_mode="HTML"
                )
            sent = True
        except Exception as e:
            print(f"❌ Админ {admin_id}: {e}")

    if sent:
        await message.answer(
            f"✅ Квитанция для заказа <b>№{order_id}</b> получена!\n"
            f"Ваш заказ будет обработан в ближайшее время.",
            parse_mode="HTML"
        )
    else:
        pending_receipts[user_id] = order_id
        await message.answer("⚠️ Не удалось переслать квитанцию. Попробуйте ещё раз.")


# ── Обычный текст — подсказка ─────────────────────────────────────────────────
@dp.message(F.text & ~F.text.startswith('/') & ~F.text.startswith('__'))
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id in pending_receipts:
        order_id = pending_receipts[user_id]
        await message.answer(
            f"📎 Для заказа <b>№{order_id}</b> отправьте "
            f"<b>фото или скриншот</b> квитанции об оплате.",
            parse_mode="HTML"
        )


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Бот запущен!")
    if not ADMIN_IDS:
        print("⚠️  ADMIN_IDS не задан!")
    else:
        print(f"✅ Админы: {ADMIN_IDS}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
