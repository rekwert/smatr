"""Шаблоны сигналов для Telegram — только русский язык."""

from __future__ import annotations

from typing import Any


def format_smc_signal(signal: dict[str, Any], ai_summary: str | None = None) -> str:
    found = (signal.get("reason") or {}).get("found") or []
    setup_lines = "\n".join(f"✅ {x}" for x in found[:6]) or "✅ Сетап обнаружен"
    return (
        "🔥 СИГНАЛ SMART MONEY\n\n"
        f"Токен: {signal.get('symbol')}\n"
        f"Направление: {signal.get('direction')}\n"
        f"Score: {signal.get('score')}/100\n"
        f"Таймфрейм: {signal.get('timeframe')}\n"
        "━━━━━━━━━━━━\n"
        f"Сетап:\n{setup_lines}\n"
        "━━━━━━━━━━━━\n"
        f"Вход: {signal.get('entry')}\n"
        f"Стоп: {signal.get('stop')}\n"
        f"Цель: {signal.get('target')}\n"
        f"RR 1:{signal.get('risk_reward')}\n"
        "━━━━━━━━━━━━\n"
        f"AI:\n{ai_summary or signal.get('explanation') or 'См. дашборд'}\n"
        "━━━━━━━━━━━━\n"
        "Только аналитика. Не финансовый совет."
    )


def format_pump_alert(signal: dict[str, Any]) -> str:
    pump = (signal.get("reason") or {}).get("pump") or {}
    reasons = pump.get("reasons") or (signal.get("reason") or {}).get("found") or []
    lines = "\n".join(f"• {r}" for r in reasons[:6])
    return (
        "🚀 РАННИЙ ПАМП\n\n"
        f"Токен: {signal.get('symbol')}\n"
        f"Pump Score: {signal.get('score')}\n"
        f"Статус: {pump.get('status', signal.get('confidence'))}\n"
        f"Причины:\n{lines}\n\n"
        "Только аналитика. Не финансовый совет."
    )


def format_early_opportunity(item: dict[str, Any]) -> str:
    reasons = "\n".join(f"✅ {r}" for r in (item.get("reasons") or [])[:6])
    return (
        "🚨 РАННЯЯ ВОЗМОЖНОСТЬ\n\n"
        f"{item.get('symbol')}\n"
        f"Биржа: {str(item.get('exchange', '')).upper()}\n"
        f"Pump Score: {item.get('score')}\n"
        f"Статус: {item.get('status')}\n"
        f"Качество: {item.get('quality')}\n\n"
        f"Почему:\n{reasons}\n\n"
        "Риск: высокий (низкая ликвидность). Только аналитический алерт."
    )


def format_invalidated(symbol: str, reason: str) -> str:
    return f"⚠️ Сетап недействителен\n\n{symbol}\nПричина: {reason}"


def format_upgrade(symbol: str, old: int, new: int) -> str:
    return f"📈 Сценарий усилен\n\n{symbol}\nScore {old} → {new}"
