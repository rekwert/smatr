"""LLM client with deterministic template fallback (Part 5)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx

from app.ai.guards import validate_ai_payload
from app.config.settings import settings

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def template_explain(context: dict[str, Any], mode: str = "explain") -> dict[str, Any]:
    symbol = context.get("symbol", "?")
    direction = context.get("direction", "?")
    score = context.get("score", 0)
    events = context.get("events") or []
    missing = context.get("missing") or []
    risk = context.get("risk") or {}
    vol = context.get("volume") or {}
    deriv = context.get("derivatives") or {}
    similar = context.get("similar") or {}
    regime = context.get("regime") or {}

    strengths = list(events)[:6] or ["Недостаточно подтверждений"]
    risks = list(missing)[:6]
    if not risks:
        risks = ["Риски определяются ближайшей ликвидностью и волатильностью"]

    if mode == "plan":
        entry = risk.get("entry")
        stop = risk.get("stop")
        explanation = (
            f"Сценарий {direction} по {symbol}.\n\n"
            f"Условия активации:\n"
            f"- удержание зоны интереса около {entry};\n"
            f"- появление подтверждающей реакции;\n"
            f"- сохранение структуры относительно стоп-уровня {stop}.\n\n"
            f"Недействительность: закрепление за уровнем {stop}.\n"
            f"Потенциал: TP около {risk.get('target')} (RR {risk.get('risk_reward')}).\n\n"
            f"Это аналитический план, не торговый приказ."
        )
        payload = {
            "summary": f"Сценарий {direction} со score {score}",
            "strengths": strengths,
            "risks": risks,
            "scenario": {
                "type": direction,
                "activation": [
                    f"Hold interest zone near {entry}",
                    "Confirmation candle / reaction",
                    "Structure preserved vs invalidation",
                ],
                "invalidation": [f"Acceptance beyond {stop}"],
                "targets": [f"TP1/TP2 toward {risk.get('target')}"],
                "conditions": ["Wait for confirmation rather than chasing impulse"],
            },
            "confidence": min(95, int(score)),
            "quality": _quality(score),
            "explanation": explanation,
        }
    elif mode == "market":
        explanation = (
            f"Контекст {symbol}: HTF={ (context.get('structure') or {}).get('htf_trend') }, "
            f"regime={ (regime or {}).get('market_regime', 'n/a') }.\n"
            f"Вероятные сценарии зависят от снятия ликвидности и сохранения/слома структуры.\n"
            f"Это описание контекста, не прогноз цены."
        )
        payload = {
            "summary": f"Рыночный контекст {symbol}",
            "strengths": strengths,
            "risks": risks,
            "scenario": {
                "type": "CONTEXT",
                "conditions": [
                    "Снятие противоположной ликвидности и продолжение",
                    "Пробой диапазона со сменой структуры",
                ],
            },
            "confidence": min(90, max(40, int(score or 60))),
            "quality": _quality(score or 60),
            "explanation": explanation,
        }
    elif mode == "similar":
        n = similar.get("sample_size", 0)
        explanation = (
            f"Похожих случаев в базе: {n}.\n"
            f"Оценка движения в сторону сетапа (прокси): {similar.get('up_probability_pct')}%.\n"
            f"Средний RR в выборке: {similar.get('average_rr')}.\n"
            f"{similar.get('note', '')}"
        )
        payload = {
            "summary": f"Найдено {n} похожих ситуаций",
            "strengths": strengths,
            "risks": risks + ["Историческая похожесть ≠ гарантия результата"],
            "scenario": {
                "type": "SIMILAR",
                "conditions": [
                    f"sample_size={n}",
                    f"up_probability_pct={similar.get('up_probability_pct')}",
                    f"average_rr={similar.get('average_rr')}",
                ],
            },
            "confidence": int(min(90, 40 + (n and 20) + (similar.get("up_probability_pct") or 0) * 0.3)),
            "quality": _quality(score),
            "explanation": explanation,
        }
    else:
        lines = [
            f"На {symbol} сформирован сценарий {direction} (score {score}/100).",
            "",
            "Основные причины:",
        ]
        for i, e in enumerate(strengths, 1):
            lines.append(f"{i}. {e}.")
        lines.append("")
        lines.append("Подтверждение:")
        if vol.get("relative_volume"):
            lines.append(f"- относительный объём x{vol.get('relative_volume')};")
        if deriv.get("oi_change_pct") is not None:
            lines.append(f"- OI {deriv.get('oi_change_pct')}%;")
        lines.append("")
        lines.append("Риски:")
        for r in risks:
            lines.append(f"- {r};")
        lines.append("")
        lines.append(f"Качество сценария: {_quality(score)}.")
        lines.append("Система не гарантирует результат.")
        payload = {
            "summary": f"Сценарий {direction} — {_quality(score)}",
            "strengths": strengths,
            "risks": risks,
            "scenario": {
                "type": direction,
                "conditions": [
                    "Сохранение структуры",
                    "Реакция в зоне интереса",
                ],
            },
            "confidence": min(95, int(score)),
            "quality": _quality(score),
            "explanation": "\n".join(lines),
        }

    return validate_ai_payload(payload)


def _quality(score: int | float) -> str:
    s = int(score or 0)
    if s >= 90:
        return "elite"
    if s >= 75:
        return "high"
    if s >= 50:
        return "medium"
    return "low"


async def call_llm(system: str, user: str, context: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not settings.llm_enabled or not settings.llm_api_key:
        return None
    base = (settings.llm_api_base or "https://api.openai.com/v1").rstrip("/")
    payload = {
        "model": settings.llm_model or "deepseek-chat",
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"{user}\n\nCONTEXT:\n{json.dumps(context, ensure_ascii=False)}",
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return validate_ai_payload(parsed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM call failed, using template: %s", exc)
        return None
