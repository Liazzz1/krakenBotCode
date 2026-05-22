import asyncio
import os
import json
import hashlib
import hmac
import time
from urllib.parse import unquote
from collections import defaultdict
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

TOKEN      = os.getenv("TOKEN")
ADMIN_IDS  = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# ─── Реквизиты банков — только в переменных окружения Railway, никогда не в коде ───
# Формат переменной BANKS_JSON (задаётся в Railway → Variables):
# {
#   "mono":   { "name": "Mono Bank",  "cards": ["4441 1110 3877 4935", "4441 1110 2281 0828", "4874 0700 2469 8423"] },
#   "myraif": { "name": "MyRaif",     "cards": ["4149 5110 2786 0675"] },
#   "sense":  { "name": "Sense Bank", "cards": ["4028 0820 1619 2153"] },
#   "pumb":   { "name": "PUMB",       "cards": ["5355 2800 4692 2306"] }
# }
try:
    BANKS: dict = json.loads(os.getenv("BANKS_JSON", "{}"))
except Exception:
    BANKS = {}

# Разрешённый Origin — твой GitHub Pages домен
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://liazzz1.github.io")

bot = Bot(token=TOKEN)
dp  = Dispatcher()

pending_receipts: dict[int, str] = {}

# ─── Rate limiting: не более 5 запросов в минуту с одного IP ───
_rate_store: dict[str, list] = defaultdict(list)
RATE_LIMIT   = 5
RATE_WINDOW  = 60  # секунд

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    calls = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
    _rate_store[ip] = calls
    if len(calls) >= RATE_LIMIT:
        return True
    _rate_store[ip].append(now)
    return False


def cors_headers(origin: str) -> dict:
    """Возвращаем Access-Control только для нашего домена."""
    allowed = origin if origin.startswith(ALLOWED_ORIGIN) else ALLOWED_ORIGIN
    return {
        "Access-Control-Allow-Origin":  allowed,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Vary": "Origin",
    }


# ═══════════════════════════════════════════════════════
#  ВЕРИФИКАЦИЯ initData от Telegram Web App
# ═══════════════════════════════════════════════════════

def verify_telegram_init_data(init_data: str) -> dict | None:
    """
    Верифицирует подпись initData по алгоритму Telegram:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

    Возвращает dict с данными пользователя или None если подпись неверна.
    """
    if not init_data or not TOKEN:
        return None

    try:
        params = {}
        for part in init_data.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = unquote(v)

        received_hash = params.pop("hash", None)
        if not received_hash:
            return None

        # Строка для проверки: пары key=value, отсортированные по ключу, через \n
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )

        # secret_key = HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_hash, received_hash):
            return None

        # Проверяем свежесть: initData не старше 1 часа
        auth_date = int(params.get("auth_date", 0))
        if time.time() - auth_date > 3600:
            return None

        user_str = params.get("user", "{}")
        return json.loads(user_str)

    except Exception as e:
        print(f"⚠️ initData verify error: {e}")
        return None


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
#  HTTP-СЕРВЕР
# ═══════════════════════════════════════════════════════

async def handle_options(request: web.Request) -> web.Response:
    """Preflight CORS."""
    origin = request.headers.get("Origin", "")
    return web.Response(status=204, headers=cors_headers(origin))


async def handle_card(request: web.Request) -> web.Response:
    """
    Возвращает реквизиты банка после верификации initData.
    POST /card  { "bank_id": "mono", "init_data": "..." }
    """
    origin = request.headers.get("Origin", "")
    ip = request.remote or "unknown"

    if is_rate_limited(ip):
        return web.json_response({"ok": False, "error": "Too many requests"},
                                 status=429, headers=cors_headers(origin))

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"},
                                 status=400, headers=cors_headers(origin))

    init_data = data.get("init_data", "")
    user = verify_telegram_init_data(init_data)
    if user is None:
        return web.json_response({"ok": False, "error": "Unauthorized"},
                                 status=401, headers=cors_headers(origin))

    bank_id = data.get("bank_id", "")
    bank = BANKS.get(bank_id)
    if not bank:
        return web.json_response({"ok": False, "error": "Unknown bank"},
                                 status=400, headers=cors_headers(origin))

    import random
    cards = bank.get("cards", [])
    card = random.choice(cards) if cards else "—"

    return web.json_response(
        {"ok": True, "name": bank["name"], "card": card},
        headers=cors_headers(origin)
    )


async def handle_order(request: web.Request) -> web.Response:
    origin = request.headers.get("Origin", "")
    ip = request.remote or "unknown"

    if is_rate_limited(ip):
        return web.json_response({"ok": False, "error": "Too many requests"},
                                 status=429, headers=cors_headers(origin))

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"},
                                 status=400, headers=cors_headers(origin))

    # ── Верификация пользователя через initData ──
    init_data = data.get("init_data", "")
    user = verify_telegram_init_data(init_data)
    if user is None:
        return web.json_response({"ok": False, "error": "Unauthorized"},
                                 status=401, headers=cors_headers(origin))

    buyer_id   = user.get("id")
    buyer_name = f"@{user['username']}" if user.get("username") else user.get("first_name", "неизвестен")

    order_id   = data.get("order_id", "???")
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
    elif order_type in ("Telegram Stars", "Telegram Premium"):
        username = data.get("username", "—")
        extra    = f"📲 TG Username: {username}\n"

    sep = "─" * 28

    admin_text = (
        f"🔔 <b>НОВЫЙ ЗАКАЗ</b>\n{sep}\n"
        f"🔑 <b>№ Заказа:</b> <code>{order_id}</code>\n"
        f"📦 <b>Тип:</b> {order_type}\n"
        f"🛍 <b>Товар:</b> {item}\n"
        f"{extra}"
        f"💳 <b>Банк:</b> {bank} | {card}\n"
        f"💰 <b>Сумма:</b> {price}\n"
        f"👤 <b>Покупатель:</b> {buyer_name} (<code>{buyer_id}</code>)\n"
        f"{sep}\n"
        f"✅ <b>Статус:</b> Ожидает выполнения"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML")
        except Exception as e:
            print(f"❌ Админ {admin_id}: {e}")

    if buyer_id:
        try:
            client_text = (
                f"🧾 <b>ВАШ ЗАКАЗ ПРИНЯТ</b>\n{sep}\n"
                f"🔑 <b>№ Заказа:</b> <code>{order_id}</code>\n"
                f"📦 <b>Тип:</b> {order_type}\n"
                f"🛍 <b>Товар:</b> {item}\n"
                f"{extra}"
                f"💰 <b>Сумма:</b> {price}\n"
                f"{sep}\n"
                f"✅ Оплата получена — обрабатываем заказ.\n\n"
                f"📎 Отправьте <b>скриншот квитанции об оплате</b> прямо сюда."
            )
            await bot.send_message(buyer_id, client_text, parse_mode="HTML")
            pending_receipts[int(buyer_id)] = order_id
            print(f"✅ Pending: client={buyer_id} order={order_id}")
        except Exception as e:
            print(f"❌ Клиент {buyer_id}: {e}")

    return web.json_response({"ok": True}, headers=cors_headers(origin))


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
    if not BANKS:
        print("⚠️  BANKS_JSON не задан — /card будет возвращать ошибку!")
    else:
        print(f"✅ Банки загружены: {list(BANKS.keys())}")

    app = web.Application()
    app.router.add_options("/order",  handle_options)
    app.router.add_options("/card",   handle_options)
    app.router.add_post("/order",     handle_order)
    app.router.add_post("/card",      handle_card)
    app.router.add_get("/health",     handle_health)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 HTTP сервер на порту {port}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
