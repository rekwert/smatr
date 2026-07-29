"""Entry Assistant API — статусы WATCH / ENTRY READY / MISSED / …"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.engines.hunter.analyzer import LowLiquidityHunter
from app.engines.pump_detector.analyzer import PumpDetector
from app.exchange_layer.market_data_engine import MarketDataEngine
from app.ml.decision import decide
from app.ml.features import extract_features
from app.ml.models import run_quant_models
from app.strategy.entry_assistant import EntryAssistant, EntryMode

router = APIRouter(prefix="/entry", tags=["entry"])


class EntryEvaluateIn(BaseModel):
    symbol: str = "BTCUSDT"
    exchange: str = "bybit"
    timeframe: str = "15m"
    mode: EntryMode = "balanced"
    oi_change_pct: Optional[float] = None


@router.post("/evaluate")
async def evaluate_entry(payload: EntryEvaluateIn):
    mde = MarketDataEngine([payload.exchange])
    try:
        candles = await mde.get_candles_as_bars(
            payload.symbol, payload.timeframe, exchange=payload.exchange, limit=150
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, detail=f"Не удалось загрузить свечи: {exc}") from exc

    oi_chg = float(payload.oi_change_pct or 0)
    if payload.oi_change_pct is None:
        try:
            oi = await mde.get_adapter(payload.exchange).get_open_interest(payload.symbol)
            if oi:
                oi_chg = float(oi.get("oi_change_pct") or 0)
        except Exception:  # noqa: BLE001
            pass

    pump = PumpDetector().analyze(candles, oi_change_pct=oi_chg)
    hunter = LowLiquidityHunter().analyze(
        payload.symbol, candles, exchange=payload.exchange, volume_24h=0, oi_change_pct=oi_chg
    )
    feats = extract_features(payload.symbol, candles, oi_change=oi_chg)
    quant = run_quant_models(feats)
    # lightweight ai score from decision without full smc again
    decision = decide(
        quant=quant,
        smc_score=float(hunter.get("score") or 0),
        hunter_score=float(pump.get("total") or 0),
        liquidity_score=float((hunter.get("components") or {}).get("liquidity_score") or 50),
    )

    result = EntryAssistant().evaluate(
        payload.symbol,
        candles,
        exchange=payload.exchange,
        mode=payload.mode,
        oi_change_pct=oi_chg,
        pump_score=float(pump.get("total") or 0),
        ai_score=float(decision.get("ai_score") or 0),
        hunter=hunter,
    )
    result["quant"] = {
        "pump_probability_pct": decision.get("pump_probability_pct"),
        "ai_score": decision.get("ai_score"),
        "risk_level": decision.get("risk_level"),
    }
    return result


@router.get("/statuses")
async def list_statuses():
    return {
        "WATCH": "Интересно, ждём",
        "SETUP_FORMING": "Сетап собирается",
        "APPROACHING_ENTRY": "Цена подходит к зоне",
        "ENTRY_READY": "Зона + триггеры — можно рассматривать вход",
        "MISSED": "Опоздали, не догонять",
        "INVALIDATED": "Сценарий сломан",
        "modes": {
            "conservative": ["liquidity_sweep", "choch", "volume"],
            "balanced": ["liquidity_sweep", "bos", "fvg", "oi"],
            "aggressive": ["compression_or_anomaly", "ai_high"],
        },
    }


@router.get("/evaluate")
async def evaluate_entry_get(
    symbol: str = Query("BTCUSDT"),
    exchange: str = Query("bybit"),
    mode: EntryMode = Query("balanced"),
    timeframe: str = Query("15m"),
):
    return await evaluate_entry(
        EntryEvaluateIn(symbol=symbol, exchange=exchange, mode=mode, timeframe=timeframe)
    )
