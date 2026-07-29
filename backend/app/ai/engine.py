"""AI Engine orchestrator (Part 5)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import build_ai_context
from app.ai.llm import call_llm, load_prompt, template_explain
from app.ai.rating import compute_final_assessment
from app.ai.similar import find_similar_setups
from app.database.models import Signal
from app.services import memory_store


class AIEngine:
    async def explain_signal(
        self,
        db: Optional[AsyncSession],
        signal: Any,
        mode: str = "explain",
    ) -> dict[str, Any]:
        signal_dict = _signal_to_dict(signal)
        similar = await find_similar_setups(db, signal_dict)
        context = build_ai_context(signal_dict, similar=similar)
        prompt_map = {
            "explain": "explain_signal.txt",
            "plan": "create_plan.txt",
            "market": "analyze_market.txt",
            "similar": "compare_setups.txt",
            "coach": "review_trade.txt",
        }
        system = load_prompt("system.txt")
        user = load_prompt(prompt_map.get(mode, "explain_signal.txt"))
        llm = await call_llm(system, user, context)
        payload = llm or template_explain(context, mode=mode if mode != "coach" else "explain")

        risk = "medium"
        if (getattr(signal, "risk_pct", None) or 0) >= 1.5:
            risk = "high"
        elif (getattr(signal, "risk_pct", None) or 0) <= 0.7:
            risk = "low"
        rating = compute_final_assessment(
            algorithm_score=int(getattr(signal, "score", 0) or 0),
            historical_probability=similar.get("up_probability_pct"),
            risk_level=risk,
            market_condition="trending",
        )
        payload["rating"] = rating
        payload["similar"] = similar
        payload["context"] = {
            "symbol": getattr(signal, "symbol", None),
            "score": getattr(signal, "score", None),
            "direction": getattr(signal, "direction", None),
        }
        payload["source"] = "llm" if llm else "template"
        return payload

    async def market_analysis(self, db: Optional[AsyncSession], symbol: str = "BTCUSDT") -> dict[str, Any]:
        row = None
        if db is not None:
            try:
                row = (
                    await db.execute(
                        select(Signal)
                        .where(Signal.symbol == symbol.upper(), Signal.status == "active")
                        .order_by(desc(Signal.score))
                        .limit(1)
                    )
                ).scalar_one_or_none()
            except Exception:  # noqa: BLE001
                row = None
        if row is None:
            mem_rows = [
                s
                for s in memory_store.list_signals(min_score=0, limit=100)
                if (s.get("symbol") or "").upper() == symbol.upper()
            ]
            if mem_rows:
                from types import SimpleNamespace

                best = max(mem_rows, key=lambda s: int(s.get("score") or 0))
                row = SimpleNamespace(**{k: best.get(k) for k in (
                    "id", "symbol", "direction", "signal_type", "score", "timeframe",
                    "entry", "stop", "target", "risk_reward", "risk_pct", "reason",
                    "zones", "explanation", "status",
                )})
                row.reason = row.reason or {}
                row.zones = row.zones or {}
        if row:
            return await self.explain_signal(db, row, mode="market")
        context = build_ai_context(
            {
                "symbol": symbol.upper(),
                "direction": "LONG",
                "score": 60,
                "timeframe": "240",
                "reason": {
                    "found": ["Insufficient active signal — contextual template"],
                    "missing": [],
                    "checklist": {},
                },
                "zones": {},
            }
        )
        return template_explain(context, mode="market")

    async def scanner_assistant(self, db: Optional[AsyncSession], min_score: int = 85) -> dict[str, Any]:
        rows: list[Any] = []
        if db is not None:
            try:
                rows = list(
                    (
                        await db.execute(
                            select(Signal)
                            .where(Signal.status == "active", Signal.score >= min_score)
                            .order_by(desc(Signal.score))
                            .limit(12)
                        )
                    ).scalars().all()
                )
            except Exception:  # noqa: BLE001
                rows = []
        if not rows:
            rows = memory_store.list_signals(min_score=min_score, limit=12)
            from types import SimpleNamespace

            rows = [SimpleNamespace(**s) for s in rows]

        best = [
            {
                "symbol": r.symbol,
                "score": r.score,
                "direction": r.direction,
                "type": getattr(r, "signal_type", None),
                "reason": ((getattr(r, "reason", None) or {}).get("found") or [])[:3],
            }
            for r in rows
        ]
        excluded = []
        for r in rows:
            missing = (getattr(r, "reason", None) or {}).get("missing") or []
            if int(getattr(r, "score", 0) or 0) < 88 and missing:
                excluded.append({"symbol": r.symbol, "reason": missing[0]})
        return {
            "summary": f"Сейчас найдено {len(best)} потенциальных сценариев",
            "best": best[:5],
            "excluded": excluded[:3],
            "explanation": (
                "Ассистент опирается на Score Engine и checklist факторов. "
                "Это не торговые рекомендации."
            ),
            "confidence": 80 if best else 40,
        }


def _signal_to_dict(signal: Any) -> dict[str, Any]:
    return {
        "id": getattr(signal, "id", None),
        "symbol": getattr(signal, "symbol", None),
        "direction": getattr(signal, "direction", None),
        "signal_type": getattr(signal, "signal_type", None),
        "score": getattr(signal, "score", None),
        "timeframe": getattr(signal, "timeframe", None),
        "entry": getattr(signal, "entry", None),
        "stop": getattr(signal, "stop", None),
        "target": getattr(signal, "target", None),
        "risk_reward": getattr(signal, "risk_reward", None),
        "risk_pct": getattr(signal, "risk_pct", None),
        "reason": getattr(signal, "reason", None) or {},
        "zones": getattr(signal, "zones", None) or {},
        "explanation": getattr(signal, "explanation", None),
    }
