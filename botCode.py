import asyncio
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import os

TOKEN    = os.getenv("TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

bot = Bot(token=TOKEN)
dp  = Dispatcher()

# Храним ожидание квитанции: { user_id: order_id }
# После того как бот попросил квитанцию — ждём фото от этого юзера
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


# ── Получаем фото или документ (квитанция) ───────────────────────────────────
@dp.message(F.photo | F.document)
async def handle_receipt(message: types.Message):
    user    = message.from_user
    user_id = user.id

    # Определяем номер заказа — либо из pending, либо ищем в подписи
    order_id = pending_receipts.pop(user_id, None)

    if not order_id:
        # Попробуем найти номер заказа в подписи к фото
        caption = message.caption or ""
        match   = re.search(r'[A-Z0-9]{6,}', caption)
        order_id = match.group(0) if match else "неизвестен"

    buyer_info = f"@{user.username}" if user.username else f"id: {user_id}"
    caption_admin = (
        f"🧾 <b>КВИТАНЦИЯ ОБ ОПЛАТЕ</b>\n"
        f"{'─' * 28}\n"
        f"🔑 <b>№ Заказа:</b> <code>{order_id}</code>\n"
        f"👤 <b>От:</b> {buyer_info} (<code>{user_id}</code>)"
    )

    # Пересылаем всем админам
    sent = False
    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(
                    admin_id,
                    photo=message.photo[-1].file_id,
                    caption=caption_admin,
                    parse_mode="HTML"
                )
            elif message.document:
                await bot.send_document(
                    admin_id,
                    document=message.document.file_id,
                    caption=caption_admin,
                    parse_mode="HTML"
                )
            sent = True
        except Exception as e:
            print(f"❌ Не удалось отправить квитанцию админу {admin_id}: {e}")

    if sent:
        await message.answer(
            "✅ Квитанция получена! Ваш заказ будет обработан в ближайшее время.",
        )
    else:
        await message.answer("⚠️ Не удалось переслать квитанцию. Попробуйте позже.")


# ── Текстовые сообщения — подсказка ─────────────────────────────────────────
@dp.message(F.text & ~F.text.startswith('/'))
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id in pending_receipts:
        await message.answer(
            "📎 Пожалуйста, отправьте <b>фото или скриншот</b> квитанции об оплате.",
            parse_mode="HTML"
        )
    # Остальные сообщения игнорируем молча


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
