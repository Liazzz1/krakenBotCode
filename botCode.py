import asyncio
import os
import json
import hashlib
import hmac
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

TOKEN      = os.getenv("TOKEN")
ADMIN_IDS  = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
# Секрет для проверки подписи запросов с фронтенда.
# Задай любую длинную случайную строку в переменных Railway: API_SECRET=...
API_SECRET = os.getenv("API_SECRET", "")

bot = Bot(token=TOKEN)
dp  = Dispatcher()

pending_receipts: dict[int, str] = {}


# ═══════════════════════════════════════════════════════
#  TELEGRAM-БОТ
# ═══════════════════════════════════════════════════════

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
                await bot.send_photo(admin_id, photo=message.photo[-1].file_id,
                                     caption=admin_caption, parse_mode="HTML")
            else:
                await bot.send_document(admin_id, document=message.document.file_id,
                                        caption=admin_caption, parse_mode="HTML")
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


@dp.message(F.text & ~F.text.startswith('/'))
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id in pending_receipts:
        order_id = pending_receipts[user_id]
        await message.answer(
            f"📎 Для заказа <b>№{order_id}</b> отправьте "
            f"<b>фото или скриншот</b> квитанции об оплате.",
            parse_mode="HTML"
        )


# ═══════════════════════════════════════════════════════
#  HTTP-СЕРВЕР (принимает заказы с фронтенда)
# ═══════════════════════════════════════════════════════

def verify_signature(body: bytes, sig_header: str) -> bool:
    """Проверяем HMAC-подпись запроса от фронтенда."""
    if not API_SECRET:
        return True  # если секрет не задан — пропускаем (для отладки)
    expected = hmac.new(API_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


async def handle_order(request: web.Request) -> web.Response:
    """
    POST /order
    Headers: X-Signature: <hmac-sha256 подпись тела>
    Body JSON: { order_id, type, item, price, buyer_id, buyer_name,
                 username?, uid?, method?, bank, card }
    """
    body = await request.read()

    # Проверка подписи
    sig = request.headers.get("X-Signature", "")
    if not verify_signature(body, sig):
        return web.json_response({"ok": False, "error": "Forbidden"}, status=403)

    try:
        data = json.loads(body)
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    order_id   = data.get("order_id", "???")
    buyer_id   = data.get("buyer_id")
    buyer_name = data.get("buyer_name", "неизвестен")
    order_type = data.get("type", "")
    item       = data.get("item", "")
    price      = data.get("price", "")
    bank       = data.get("bank", "")
    card       = data.get("card", "")

    extra = ""
    if order_type == "PUBG UC":
        method = data.get("method", "—")
        uid    = data.get("uid", "")
        extra  = f"🎮 Метод: {method}\n" + (f"🆔 Game ID: {uid}\n" if uid else "")
    elif order_type == "Telegram Stars":
        username = data.get("username", "—")
        extra    = f"📲 TG Username: {username}\n"

    sep = "─" * 28

    admin_text = (
        f"🔔 НОВЫЙ ЗАКАЗ\n{sep}\n"
        f"🔑 № Заказа: {order_id}\n"
        f"📦 Тип: {order_type}\n"
        f"🛍 Товар: {item}\n"
        f"{extra}"
        f"💳 Банк: {bank} | {card}\n"
        f"💰 Сумма: {price}\n"
        f"👤 Покупатель: {buyer_name} ({buyer_id})\n"
        f"{sep}\n"
        f"✅ Статус: Ожидает выполнения"
    )

    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception as e:
            print(f"❌ Админ {admin_id}: {e}")

    # Пишем клиенту "Заказ принят" и запрашиваем квитанцию
    if buyer_id:
        try:
            client_text = (
                f"🧾 ВАШ ЗАКАЗ ПРИНЯТ\n{sep}\n"
                f"🔑 № Заказа: {order_id}\n"
                f"📦 Тип: {order_type}\n"
                f"🛍 Товар: {item}\n"
                f"{extra}"
                f"💰 Сумма: {price}\n"
                f"{sep}\n"
                f"✅ Оплата получена — обрабатываем заказ.\n\n"
                f"📎 Пожалуйста, отправьте <b>скриншот квитанции об оплате</b> прямо сюда."
            )
            await bot.send_message(buyer_id, client_text, parse_mode="HTML")
            pending_receipts[int(buyer_id)] = order_id
            print(f"✅ Pending: client={buyer_id} order={order_id}")
        except Exception as e:
            print(f"❌ Клиент {buyer_id}: {e}")

    return web.json_response({"ok": True})


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


# ═══════════════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════════════

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Бот запущен!")
    if not ADMIN_IDS:
        print("⚠️  ADMIN_IDS не задан!")
    else:
        print(f"✅ Админы: {ADMIN_IDS}")
    if not API_SECRET:
        print("⚠️  API_SECRET не задан — подписи не проверяются!")

    # Запускаем HTTP-сервер рядом с ботом
    app = web.Application()
    app.router.add_post("/order", handle_order)
    app.router.add_get("/health", handle_health)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 HTTP сервер запущен на порту {port}")

    # Запускаем polling бота параллельно
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
