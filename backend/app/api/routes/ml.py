"""Part 13 Quant AI + Decision endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.engines.hunter.analyzer import LowLiquidityHunter
from app.engines.scoring.calculator import ScoreCalculator
from app.engines.structure.analyzer import StructureAnalyzer
from app.exchange_layer.market_data_engine import MarketDataEngine
from app.ml.decision import decide
from app.ml.features import extract_features
from app.ml.models import run_quant_models

router = APIRouter(prefix="/ml", tags=["ml"])


class AnalyzeIn(BaseModel):
    symbol: str = "BTCUSDT"
    exchange: str = "bybit"
    timeframe: str = "15m"


@router.post("/analyze")
async def ml_analyze(payload: AnalyzeIn):
    mde = MarketDataEngine([payload.exchange])
    try:
        bars = await mde.get_candles_as_bars(
            payload.symbol, payload.timeframe, exchange=payload.exchange, limit=150
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, detail=str(exc)) from exc

    oi_chg = 0.0
    funding = None
    imbalance = None
    spread = None
    try:
        adapter = mde.get_adapter(payload.exchange)
        oi = await adapter.get_open_interest(payload.symbol)
        if oi:
            oi_chg = float(oi.get("oi_change_pct") or 0)
        funding = await adapter.get_funding_rate(payload.symbol)
        book = await adapter.get_orderbook(payload.symbol, limit=20)
        from app.market_data.orderbook import compute_orderbook_metrics

        m = compute_orderbook_metrics(book.to_dict())
        imbalance = m.get("imbalance")
        spread = m.get("spread_pct")
    except Exception:  # noqa: BLE001
        pass

    # BTC context
    btc_trend = "unknown"
    try:
        btc_bars = await mde.get_candles_as_bars("BTCUSDT", "4h", exchange="bybit", limit=80)
        st = StructureAnalyzer()
        btc_trend = st.current_trend(st.find_swings(btc_bars))
    except Exception:  # noqa: BLE001
        pass

    feats = extract_features(
        payload.symbol,
        bars,
        oi_change=oi_chg,
        funding=funding,
        orderbook_imbalance=imbalance,
        spread_pct=spread,
        btc_trend=btc_trend,
    )
    quant = run_quant_models(feats)
    smc = ScoreCalculator().analyze_symbol(payload.symbol, bars)
    hunter = LowLiquidityHunter().analyze(payload.symbol, bars, exchange=payload.exchange)
    decision = decide(
        quant=quant,
        smc_score=smc.get("score") or 0,
        hunter_score=hunter.get("score") or 0,
        liquidity_score=(hunter.get("components") or {}).get("liquidity_score") or 50,
    )
    return {
        "features": feats,
        "quant": quant,
        "smc_score": smc.get("score"),
        "hunter_score": hunter.get("score"),
        "decision": decision,
    }
