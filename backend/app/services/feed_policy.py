"""Product feed policy — inefficiency-first ranking & gates.

Main feed = market inefficiencies (Sweep + FVG + OB), ranked by Edge → Execution → Setup.
Majors allowed only with a much higher Edge threshold.
"""

from __future__ import annotations

from typing import Any, Optional

# Liquid majors — not banned, but need rare/strong inefficiency (high Edge)
MAJOR_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "TRXUSDT",
    "TONUSDT",
    "SUIUSDT",
}

# Default product feed ("best opportunities")
MIN_EDGE_BEST = 70
MIN_EDGE_MAJOR = 85
MIN_SETUP_BEST = 55
MIN_EXEC_SOFT = 30  # soft preference, not hard kill if edge strong

# Component / checklist thresholds for structural gate
COMP_OK = 50


def is_major(symbol: str) -> bool:
    return str(symbol or "").upper() in MAJOR_SYMBOLS


def _comp(components: dict[str, Any], key: str) -> float:
    try:
        return float(components.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def structural_gate(
    *,
    checklist: Optional[dict[str, bool]] = None,
    components: Optional[dict[str, float]] = None,
    flash_ok: bool = False,
) -> tuple[bool, list[str]]:
    """Require Liquidity Sweep + (FVG and Order Block), or strong flash inefficiency."""
    cl = checklist or {}
    comps = components or {}
    missing: list[str] = []

    sweep = bool(cl.get("liquidity_sweep")) or _comp(comps, "liquidity_sweep") >= COMP_OK
    fvg = bool(cl.get("fvg")) or _comp(comps, "fvg") >= COMP_OK
    ob = bool(cl.get("order_block")) or _comp(comps, "order_block") >= COMP_OK

    # Flash spike / wick revert can substitute as structural confirmation
    # still require a sweep OR flash as the inefficiency trigger
    if flash_ok and (fvg or ob or sweep):
        if not sweep and not flash_ok:
            missing.append("Liquidity Sweep")
        return (True, [])

    if flash_ok and (_comp(comps, "liquidity_sweep") >= 40 or sweep):
        return True, []

    if not sweep:
        missing.append("Liquidity Sweep")
    if not fvg:
        missing.append("FVG")
    if not ob:
        missing.append("Order Block")

    if flash_ok and sweep and (fvg or ob):
        return True, []

    ok = sweep and fvg and ob
    return ok, missing


def edge_threshold_for(symbol: str, *, mode: str = "best") -> int:
    if mode == "all":
        return 0
    return MIN_EDGE_MAJOR if is_major(symbol) else MIN_EDGE_BEST


def passes_inefficiency_persist(
    analysis: dict[str, Any],
    *,
    flash_ok: bool = False,
) -> tuple[bool, str]:
    """Gate used when writing to product feed / memory / PG."""
    reasons = analysis.get("reasons") or {}
    checklist = reasons.get("checklist") if isinstance(reasons, dict) else {}
    components = analysis.get("components") or {}
    if isinstance(reasons, dict) and not components:
        components = reasons.get("components") or {}

    ok, missing = structural_gate(
        checklist=checklist if isinstance(checklist, dict) else {},
        components=components if isinstance(components, dict) else {},
        flash_ok=flash_ok,
    )
    if not ok:
        return False, "Нет структуры неэффективности: " + ", ".join(missing)

    edge = int(analysis.get("edge_score") or 0)
    setup = int(analysis.get("setup_score") or analysis.get("score") or 0)
    symbol = str(analysis.get("symbol") or "")
    need = edge_threshold_for(symbol, mode="best")
    if edge < need:
        kind = "мажор" if is_major(symbol) else "сетап"
        return False, f"Edge {edge} < порог {need} для {kind}"
    if setup < MIN_SETUP_BEST and not flash_ok:
        return False, f"Setup {setup} < {MIN_SETUP_BEST}"
    return True, "ok"


def _pick_num(row: dict[str, Any], *keys: str, default: float = 0) -> float:
    reason = row.get("reason") if isinstance(row.get("reason"), dict) else {}
    for k in keys:
        if row.get(k) is not None:
            try:
                return float(row[k])
            except (TypeError, ValueError):
                pass
        if reason.get(k) is not None:
            try:
                return float(reason[k])
            except (TypeError, ValueError):
                pass
    return default


def signal_sort_key(row: dict[str, Any]) -> tuple:
    """Edge → Execution → Setup (desc)."""
    edge = _pick_num(row, "edge_score")
    exe = _pick_num(row, "execution_score")
    setup = _pick_num(row, "setup_score", "score")
    return (-edge, -exe, -setup)


def filter_feed_rows(
    rows: list[dict[str, Any]],
    *,
    mode: str = "best",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    mode=best → inefficiency product feed
    mode=all  → everything active (legacy / debug)
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        if mode == "all":
            out.append(r)
            continue

        symbol = str(r.get("symbol") or "")
        reason = r.get("reason") if isinstance(r.get("reason"), dict) else {}
        comps = reason.get("components") or {}
        checklist = reason.get("checklist") or {}
        flash_ok = bool(
            reason.get("flash_inefficiency")
            or r.get("flash_inefficiency")
            or (r.get("signal_type") == "flash")
        )
        ok, _ = structural_gate(
            checklist=checklist if isinstance(checklist, dict) else {},
            components=comps if isinstance(comps, dict) else {},
            flash_ok=flash_ok,
        )
        if not ok:
            # Also accept rows already tagged as inefficiency source with edge
            src = str(reason.get("feed_source") or r.get("feed_source") or "")
            if src not in ("universe_v2", "inefficiency", "flash") and not reason.get("inefficiency_ok"):
                continue
            if not ok:
                continue

        edge = _pick_num(r, "edge_score")
        if edge < edge_threshold_for(symbol, mode=mode):
            continue
        setup = _pick_num(r, "setup_score", "score")
        if setup < MIN_SETUP_BEST and not flash_ok:
            continue
        out.append(r)

    out.sort(key=signal_sort_key)
    return out[:limit]


def annotate_inefficiency(analysis: dict[str, Any], *, flash: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Stamp analysis for feed tagging."""
    flash_ok = bool(flash and flash.get("detected"))
    ok, msg = passes_inefficiency_persist(analysis, flash_ok=flash_ok)
    analysis["inefficiency_ok"] = ok
    analysis["inefficiency_gate"] = msg
    analysis["feed_source"] = "inefficiency" if ok else analysis.get("feed_source") or "smc"
    if flash_ok:
        analysis["flash_inefficiency"] = flash
        if ok:
            analysis["signal_type_hint"] = "flash"
    return analysis
