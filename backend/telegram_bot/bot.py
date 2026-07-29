from __future__ import annotations

"""Telegram-бот SMAS (aiogram 3) — интерфейс на русском.

Запуск:
  python -m telegram_bot.bot
Нужны TELEGRAM_BOT_TOKEN и SMAS_API_URL.
"""

import asyncio
import logging
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smas.telegram")

API_URL = os.getenv("SMAS_API_URL", "http://localhost:8000")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEB_BASE = os.getenv("SMAS_WEB_URL", "http://localhost:3001")


def kb_signal(signal_id: int, symbol: str = "") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📊 График", callback_data=f"chart:{signal_id}:{symbol}"),
            InlineKeyboardButton(text="📋 План", callback_data=f"plan:{signal_id}"),
            InlineKeyboardButton(text="⏭ Пропуск", callback_data=f"fb:skip:{signal_id}"),
        ],
        [
            InlineKeyboardButton(text="AI-разбор", callback_data=f"ai:{signal_id}"),
            InlineKeyboardButton(text="Похожие", callback_data=f"sim:{signal_id}"),
        ],
        [
            InlineKeyboardButton(text="👍", callback_data=f"fb:up:{signal_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"fb:down:{signal_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def api_get(path: str):
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"{API_URL}{path}")
        r.raise_for_status()
        return r.json()


async def api_post(path: str, json: dict | None = None):
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{API_URL}{path}", json=json or {})
        r.raise_for_status()
        return r.json()


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start(message: Message):
        await message.answer(
            "Добро пожаловать в Smart Money AI Scanner.\n\n"
            "Ваш аккаунт подключен.\n"
            "Режим: Scanner Mode\n\n"
            "Команды:\n"
            "/scan — сканирование рынка\n"
            "/scanner — то же, что /scan\n"
            "/signals — активные сигналы\n"
            "/positions — сценарии на наблюдении\n"
            "/risk — сводка риска\n"
            "/analyze SYMBOL — AI-контекст\n"
            "/settings — настройки\n\n"
            "Биржа: Bybit Linear. Это аналитика, не финансовые советы."
        )

    @dp.message(Command("signals"))
    async def signals(message: Message):
        data = await api_get("/api/v1/signals?min_score=80&limit=10")
        if not data:
            await message.answer("Активных сигналов нет.")
            return
        lines = ["🔥 АКТИВНЫЕ СИГНАЛЫ\n"]
        for i, s in enumerate(data[:10], 1):
            lines.append(f"{i}. {s['symbol']}  Score {s['score']}  {s['direction']}")
        first = data[0]
        await message.answer(
            "\n".join(lines),
            reply_markup=kb_signal(first["id"], first.get("symbol", "")),
        )

    async def _run_scan(message: Message):
        await message.answer("Ищем по топ-объёму Bybit…")
        result = await api_post("/api/v1/scanner/run?limit=15&timeframe=15")
        await message.answer(f"Создано сигналов: {result.get('created', 0)}")

    @dp.message(Command("scan"))
    async def scan(message: Message):
        await _run_scan(message)

    @dp.message(Command("scanner"))
    async def scanner(message: Message):
        await _run_scan(message)

    @dp.message(Command("positions"))
    async def positions(message: Message):
        data = await api_get("/api/v1/signals?min_score=70&limit=15")
        active = [s for s in (data or []) if s.get("status") == "active"]
        if not active:
            await message.answer("Открытых сценариев нет (режим подтверждения, без live-ордеров).")
            return
        lines = ["📌 НАБЛЮДЕНИЕ (MVP)\n"]
        for s in active[:10]:
            lines.append(
                f"{s['symbol']} {s['direction']} · вход {s.get('entry')} · "
                f"стоп {s.get('stop')} · score {s['score']}"
            )
        await message.answer("\n".join(lines))

    @dp.message(Command("risk"))
    async def risk(message: Message):
        await message.answer(
            "⚠ РИСК АККАУНТА\n\n"
            "Режим: подтверждение вручную (автоторговля выкл.)\n"
            "Риск на сделку по умолчанию: 1%\n"
            "Мин. RR: 2.5\n"
            "Дневной лимит убытка: см. настройки web\n\n"
            "Не рискуйте капиталом, который не готовы потерять."
        )

    @dp.message(Command("analyze"))
    async def analyze(message: Message):
        parts = (message.text or "").split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTCUSDT"
        data = await api_post("/api/v1/ai/market-analysis", {"symbol": symbol})
        await message.answer(data.get("explanation") or data.get("summary") or str(data))

    @dp.message(Command("settings"))
    async def settings_cmd(message: Message):
        await message.answer(
            "⚙ Настройки алертов\n\n"
            "• мин. score по умолчанию: 90\n"
            "• notify_smc / notify_pumps\n"
            "• cooldown: 30 мин на монету\n\n"
            "Изменение: веб → Настройки или API /api/v1/notifications/settings"
        )

    @dp.callback_query(F.data.startswith("ai:"))
    async def cb_ai(call: CallbackQuery):
        signal_id = int(call.data.split(":")[1])
        data = await api_post("/api/v1/ai/explain", {"signal_id": signal_id})
        await call.message.answer(data.get("explanation") or data.get("summary", "Нет объяснения"))
        await call.answer()

    @dp.callback_query(F.data.startswith("plan:"))
    async def cb_plan(call: CallbackQuery):
        signal_id = int(call.data.split(":")[1])
        data = await api_post("/api/v1/ai/explain", {"signal_id": signal_id, "mode": "plan"})
        await call.message.answer(data.get("explanation") or data.get("summary", "План недоступен"))
        await call.answer()

    @dp.callback_query(F.data.startswith("chart:"))
    async def cb_chart(call: CallbackQuery):
        parts = call.data.split(":")
        symbol = parts[2] if len(parts) > 2 else ""
        url = f"{WEB_BASE}/terminal?symbol={symbol}" if symbol else f"{WEB_BASE}/terminal"
        await call.message.answer(f"📊 График: {url}")
        await call.answer()

    @dp.callback_query(F.data.startswith("sim:"))
    async def cb_sim(call: CallbackQuery):
        signal_id = int(call.data.split(":")[1])
        data = await api_post("/api/v1/ai/explain", {"signal_id": signal_id, "mode": "similar"})
        sim = data.get("similar") or {}
        text = (
            f"Похожих сетапов: {sim.get('sample_size')}\n"
            f"Прокси вверх: {sim.get('up_probability_pct')}%\n"
            f"Средний RR: {sim.get('average_rr')}\n\n"
            f"{data.get('explanation', '')}"
        )
        await call.message.answer(text)
        await call.answer()

    @dp.callback_query(F.data.startswith("fb:"))
    async def cb_fb(call: CallbackQuery):
        _, vote, sid = call.data.split(":")
        await api_post(
            "/api/v1/notifications/feedback",
            {"signal_id": int(sid), "vote": vote, "telegram_id": call.from_user.id},
        )
        await call.answer("Спасибо за отзыв")

    return dp


async def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN обязателен")
    bot = Bot(TOKEN)
    dp = create_dispatcher()
    logger.info("Telegram-бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
