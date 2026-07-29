"""Hallucination / language guards (Part 5 §7)."""

from __future__ import annotations

import re
from typing import Any

FORBIDDEN_PATTERNS = [
    r"\b100%\b",
    r"точно выраст",
    r"гарантирован",
    r"покупай сейчас",
    r"продавай сейчас",
    r"\bmust buy\b",
    r"\bguaranteed\b",
]


def sanitize_text(text: str) -> str:
    cleaned = text
    for pat in FORBIDDEN_PATTERNS:
        cleaned = re.sub(pat, "[вероятностный сценарий]", cleaned, flags=re.IGNORECASE)
    return cleaned


def validate_ai_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    for key in ("summary", "explanation"):
        if isinstance(out.get(key), str):
            out[key] = sanitize_text(out[key])
    for key in ("strengths", "risks"):
        if isinstance(out.get(key), list):
            out[key] = [sanitize_text(str(x)) for x in out[key]]
    scenario = out.get("scenario")
    if isinstance(scenario, dict):
        for field in ("conditions", "activation", "invalidation", "targets"):
            if isinstance(scenario.get(field), list):
                scenario[field] = [sanitize_text(str(x)) for x in scenario[field]]
        out["scenario"] = scenario
    conf = out.get("confidence")
    if conf is None:
        out["confidence"] = 50
    else:
        out["confidence"] = int(max(0, min(100, float(conf))))
    return out
