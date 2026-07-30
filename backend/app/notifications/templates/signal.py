"""Шаблоны сигналов для Telegram — только русский язык."""

from __future__ import annotations

from typing import Any


def format_inefficiency_ready(signal: dict[str, Any]) -> str:
    """Telegram alert when inefficiency playbook reaches ENTRY READY."""
    pb = signal.get("inefficiency_playbook") or []
    steps = "\n".join(
        f"{'✅' if s.get('done') else '□'} {s.get('label')}" for s in pb[:5]
    ) or "✅ Условия входа"
    plan = signal.get("inefficiency_plan") or {}
    entry_lo = plan.get("entry_low") or signal.get("ideal_entry_low") or signal.get("entry")
    entry_hi = plan.get("entry_high") or signal.get("ideal_entry_high") or signal.get("entry")
    stop = plan.get("stop") or signal.get("stop")
    tp1 = plan.get("tp1") or signal.get("tp1") or signal.get("target")
    return (
        "🟢 НЕЭФФЕКТИВНОСТЬ · ВХОД\n\n"
        f"Токен: {signal.get('symbol')} ({str(signal.get('exchange') or 'bybit').upper()})\n"
        f"Направление: {signal.get('direction')}\n"
        f"Тип: {signal.get('inefficiency_type_ru') or signal.get('inefficiency_type') or '—'}\n"
        f"Edge: {signal.get('edge_score')} · RV×{signal.get('relative_volume')}\n"
        f"Статус: {signal.get('inefficiency_status_ru') or 'Можно искать вход'}\n"
        "━━━━━━━━━━━━\n"
        f"Playbook:\n{steps}\n"
        "━━━━━━━━━━━━\n"
        f"Зона: {entry_lo} – {entry_hi}\n"
        f"Stop: {stop}\n"
        f"TP1: {tp1}\n"
        f"RR: {plan.get('risk_reward') or signal.get('risk_reward')}\n"
        "━━━━━━━━━━━━\n"
        f"{(signal.get('inefficiency_thesis') or signal.get('ai_conclusion') or '')[:220]}\n"
        "━━━━━━━━━━━━\n"
        "Только аналитика. Не финансовый совет. Без автоторговли."
    )


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
