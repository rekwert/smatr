"""AI Explanation Engine — template now, LLM optional (Part 1 scenario 3 / Part 4 §8)."""

from __future__ import annotations

from typing import Any, Optional

from app.config.settings import settings


def build_explanation(analysis: dict[str, Any], pump: Optional[dict[str, Any]] = None) -> str:
    symbol = analysis.get("symbol", "?")
    tf = analysis.get("timeframe", "?")
    direction = analysis.get("direction", "?")
    score = analysis.get("score", 0)
    reasons = analysis.get("reasons") or {}
    found = reasons.get("found") or []
    missing = reasons.get("missing") or []
    levels = analysis.get("levels") or {}
    market = analysis.get("market") or {}

    lines = [
        f"На таймфрейме {tf} по {symbol} сформирован сценарий {direction} (score {score}/100).",
        "",
        "Почему сценарий найден:",
    ]
    if found:
        for i, item in enumerate(found, 1):
            lines.append(f"{i}. {item}.")
    else:
        lines.append("1. Недостаточно подтверждённых факторов последовательности.")

    lines.append("")
    lines.append("Сильные стороны:")
    for item in found[:5]:
        lines.append(f"+ {item}")

    lines.append("")
    lines.append("Риски / чего не хватает:")
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- Критичных отсутствующих факторов не видно.")

    if market.get("htf_trend"):
        lines.append(f"- HTF trend: {market['htf_trend']}.")
    if market.get("funding") is not None:
        lines.append(f"- Funding: {market['funding']}.")

    if levels.get("entry") is not None:
        lines.append("")
        lines.append(
            f"Уровни (аналитические, не призыв к действию): "
            f"entry {levels.get('entry')}, stop {levels.get('stop')}, "
            f"TP2 {levels.get('tp2')}, RR {levels.get('risk_reward')}."
        )

    if pump and pump.get("total", 0) >= 70:
        lines.append("")
        lines.append(
            f"Дополнительно Pump Detector: score {pump['total']}, status={pump.get('status')}."
        )
        for r in pump.get("reasons") or []:
            lines.append(f"• {r}")

    lines.append("")
    lines.append(
        "Вывод: система помогает структурировать анализ. "
        "Это не гарантия прибыли и не автоматическая торговая рекомендация."
    )
    return "\n".join(lines)


async def explain_with_llm(analysis: dict[str, Any]) -> Optional[str]:
    if not settings.llm_enabled or not settings.llm_api_key:
        return None
    # Placeholder for Part 5 / later LLM wiring
    return None
