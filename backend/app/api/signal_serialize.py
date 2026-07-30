"""Serialize Signal ORM / memory dict → SignalOut with dual-score fields."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.api.schemas import SignalOut
from app.engines.scoring.readiness import STATUS_META, build_readiness_payload


def _pick(reason: dict[str, Any], row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict) and row.get(key) is not None:
        return row.get(key)
    if reason.get(key) is not None:
        return reason.get(key)
    return default


def _parse_created(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _synthetic_components(reason: dict[str, Any], score: Any) -> dict[str, float]:
    """Fallback when Universe v2 stored score without SMC component breakdown."""
    smc = float(reason.get("smc_score") or score or 50)
    base = max(20.0, min(92.0, smc))
    liq = float(reason.get("liquidity_score") or 25)
    pump = float(reason.get("pump_probability_pct") or 40)
    vol = max(15.0, min(85.0, liq * 1.8))
    oi = max(10.0, min(70.0, pump * 0.55))
    return {
        "liquidity_sweep": base * 0.90,
        "fvg": base * 0.88,
        "order_block": base * 0.85,
        "bos": base * 0.35,  # confirmation only — not the thesis
        "htf_trend": base * 0.70,
        "volume": vol,
        "oi": oi,
    }


def _backfill_readiness(data: dict[str, Any], reason: dict[str, Any]) -> dict[str, Any]:
    components = reason.get("components") or {}
    if not isinstance(components, dict) or not components:
        # Universe v2 / legacy rows: synthesize so card metrics are not blank
        if reason.get("universe_v2") or data.get("setup_score") or data.get("score"):
            components = _synthetic_components(reason, data.get("setup_score") or data.get("score"))
        else:
            return {}

    checklist = reason.get("checklist") or {}
    if not checklist:
        checklist = {
            k: float(components.get(k) or 0) >= 50
            for k in (
                "liquidity_sweep",
                "bos",
                "fvg",
                "order_block",
                "htf_trend",
                "volume",
                "oi",
            )
        }

    zones = data.get("zones") or {}
    pd = zones.get("premium_discount") if isinstance(zones, dict) else None
    direction = str(data.get("direction") or "LONG")
    seq = (
        float(components.get("bos") or 0) >= 50
        or float(components.get("liquidity_sweep") or 0) >= 50
    ) and (
        float(components.get("fvg") or 0) >= 40
        or float(components.get("order_block") or 0) >= 40
    )
    entry = data.get("entry")
    current = (
        (reason.get("market") or {}).get("current_price")
        if isinstance(reason.get("market"), dict)
        else None
    )
    if current is None:
        current = data.get("current_price") or entry

    # Soft PD estimate when universe row has no zones (keeps Range usable)
    if not isinstance(pd, dict) and current is not None:
        px = float(current)
        pd = {
            "zone": "equilibrium",
            "high": px * 1.04,
            "low": px * 0.96,
            "mid": px,
        }

    return build_readiness_payload(
        direction=direction,
        components={k: float(v or 0) for k, v in components.items()},
        checklist=checklist,
        sequence_valid=seq,
        pd=pd if isinstance(pd, dict) else {},
        zones=zones if isinstance(zones, dict) else {},
        regime=reason.get("regime") if isinstance(reason.get("regime"), dict) else None,
        entry=float(entry) if entry is not None else None,
        current_price=float(current) if current is not None else None,
        created_at=_parse_created(data.get("created_at")),
        tp1=reason.get("tp1"),
        tp2=data.get("target"),
        stop=data.get("stop"),
        risk_reward=data.get("risk_reward"),
        volume_24h=(
            float((reason.get("market") or {}).get("volume_24h"))
            if isinstance(reason.get("market"), dict) and (reason.get("market") or {}).get("volume_24h") is not None
            else float(reason["liquidity_score"]) * 1_000_000
            if reason.get("liquidity_score") is not None
            else None
        ),
        previous={
            "score_history": data.get("score_history"),
            "replay": data.get("replay"),
            "execution_score": data.get("execution_score"),
            "setup_score": data.get("setup_score"),
            "timing": data.get("timing"),
            "lifecycle_status": data.get("lifecycle_status"),
            "execution_breakdown": data.get("execution_breakdown"),
            "action": data.get("action"),
        }
        if data.get("score_history") or data.get("replay") or data.get("lifecycle_status")
        else None,
    )


def to_signal_out(row: Any) -> SignalOut:
    if isinstance(row, SignalOut):
        return row

    if isinstance(row, dict):
        data = dict(row)
        reason = data.get("reason") or {}
    else:
        data = {
            "id": row.id,
            "symbol": row.symbol,
            "exchange": getattr(row, "exchange", None) or "bybit",
            "direction": row.direction,
            "signal_type": row.signal_type,
            "score": row.score,
            "confidence": row.confidence,
            "timeframe": row.timeframe,
            "entry": row.entry,
            "stop": row.stop,
            "target": row.target,
            "risk_reward": row.risk_reward,
            "risk_pct": row.risk_pct,
            "reason": row.reason or {},
            "zones": row.zones or {},
            "explanation": row.explanation,
            "status": row.status,
            "created_at": row.created_at,
        }
        reason = data["reason"] or {}

    # Hoist analyzable history stored inside reason JSONB (Postgres path)
    if isinstance(reason, dict):
        data.setdefault("score_history", reason.get("score_history"))
        data.setdefault("replay", reason.get("replay"))
        data.setdefault("setup_score", reason.get("setup_score"))
        data.setdefault("execution_score", reason.get("execution_score"))
        data.setdefault("edge_score", reason.get("edge_score"))
        data.setdefault("edge_reasons", reason.get("edge_reasons"))
        data.setdefault("timing", reason.get("timing"))
        data.setdefault("lifecycle_status", reason.get("lifecycle_status"))
        data.setdefault("feed", reason.get("feed") or data.get("feed"))
        if isinstance(reason.get("checklist"), dict):
            data.setdefault("checklist", reason.get("checklist"))
        if isinstance(reason.get("components"), dict) and not data.get("components"):
            data["components"] = reason.get("components")

    readiness = {}
    # Always try backfill: real components OR synthetic for universe_v2/legacy
    if reason.get("components") or reason.get("universe_v2") or reason.get("smc_score") is not None:
        readiness = _backfill_readiness(data, reason)
    elif not data.get("execution_score") and (data.get("score") or data.get("setup_score")):
        readiness = _backfill_readiness(data, reason)

    # Force recompute from components when we have them (fixes Execution=0 on old rows)
    if readiness:
        for k in (
            "timing",
            "timing_emoji",
            "timing_ru",
            "timing_reason",
            "traffic_lights",
            "execution_breakdown",
            "ideal_entry",
            "ideal_entry_low",
            "ideal_entry_high",
            "alternative_entry_low",
            "alternative_entry_high",
            "pd_zone",
            "ai_verdict",
            "status_reason",
            "waiting_for",
            "next_steps",
            "ai_comment",
            "ai_conclusion",
            "zone_note",
            "why_no_entry",
            "invalidation",
            "confidence_drivers",
            "next_trigger",
            "range_scale",
            "scenario_probability",
            "entry_probability_now",
            "liquidity_quality",
            "liquidity_stars",
            "liquidity_hint",
            "chasing_risk",
            "chasing_level",
            "chasing_level_ru",
            "chasing_hint",
            "smart_money_activity",
            "smart_money_ru",
            "smart_money_score",
            "smart_money_stars",
            "smart_money_hint",
            "edge_score",
            "edge_stars",
            "edge_reasons",
            "edge_hint",
            "replay",
            "risk_label",
            "scenario_risk_pct",
            "current_price",
            "distance_pct",
            "distance_label",
            "action",
            "freshness",
            "freshness_ru",
            "age_sec",
            "age_label",
            "reeval_sec",
            "tp1",
            "tp2",
            "stop",
            "plan_valid",
            "plan_note",
            "invalidation_level",
            "setup_score",
            "execution_score",
            "overall_score",
            "overall_formula",
            "setup_stars",
            "execution_stars",
            "probability",
            "lifecycle_status",
            "lifecycle_emoji",
            "lifecycle_ru",
            "lifecycle_hint",
            "phase",
            "phase_ru",
        ):
            if readiness.get(k) is not None:
                data[k] = readiness[k]
        # Preserve live history from memory if present
        if data.get("score_history") is None and readiness.get("score_history") is not None:
            data["score_history"] = readiness["score_history"]
        # Preserve / seed replay timeline
        if readiness.get("replay"):
            if data.get("replay"):
                # Prefer longer memory replay if richer
                if len(data.get("replay") or []) < len(readiness["replay"]):
                    data["replay"] = readiness["replay"]
            else:
                data["replay"] = readiness["replay"]
        data.setdefault("edge_score", readiness.get("edge_score"))
        data.setdefault("edge_stars", readiness.get("edge_stars"))
        data.setdefault("edge_reasons", readiness.get("edge_reasons"))
        data.setdefault("edge_hint", readiness.get("edge_hint"))
        # Ideal entry overrides flat entry when present; keep normalized stop/TP
        if readiness.get("ideal_entry") is not None:
            data["entry"] = readiness.get("entry") or readiness["ideal_entry"]
            data["ideal_entry"] = readiness["ideal_entry"]
        if readiness.get("stop") is not None:
            data["stop"] = readiness["stop"]
        if readiness.get("tp1") is not None:
            data["tp1"] = readiness["tp1"]
        if readiness.get("tp2") is not None:
            data["target"] = readiness["tp2"]
        if readiness.get("risk_reward") is not None:
            data["risk_reward"] = readiness["risk_reward"]

        reason = dict(reason)
        orig_found = list(reason.get("found") or [])
        ready_confirmed = list(readiness.get("confirmed") or [])
        # Keep universe hunter reasons visible; append SMC confirms
        merged: list[str] = []
        for item in (ready_confirmed + orig_found) if not reason.get("universe_v2") else (orig_found + ready_confirmed):
            if item and item not in merged:
                merged.append(item)
        reason["confirmed"] = merged or ready_confirmed or orig_found
        reason["missing_items"] = readiness.get("missing_items") or []
        reason["found"] = reason["confirmed"]
        reason["missing"] = reason["missing_items"]
        # Keep components so next serialize can use real/synth consistently
        if readiness.get("execution_components") is None and not reason.get("components"):
            pass
        data["reason"] = reason
    else:
        status = _pick(reason, data, "lifecycle_status")
        meta = STATUS_META.get(str(status or ""), {})
        data["setup_score"] = _pick(reason, data, "setup_score", data.get("score"))
        data["execution_score"] = _pick(reason, data, "execution_score", 0)
        data["lifecycle_status"] = status
        data["lifecycle_emoji"] = _pick(reason, data, "lifecycle_emoji", meta.get("emoji"))
        data["lifecycle_ru"] = _pick(reason, data, "lifecycle_ru", meta.get("ru"))

    data.setdefault("ai_comment", data.get("ai_conclusion") or data.get("explanation"))
    data.setdefault("ai_conclusion", data.get("ai_comment"))
    data.setdefault("reeval_sec", 60)
    data.setdefault("exchange", "bybit")
    if data.get("tp1") is None:
        data["tp1"] = reason.get("tp1")

    return SignalOut.model_validate(data)
