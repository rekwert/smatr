from fastapi import APIRouter

from app.api.routes import (
    ai,
    auth,
    backtest,
    charts,
    data,
    entry,
    exchanges,
    market,
    ml,
    notifications,
    pump_hunter,
    scanner,
    signals,
    trade_plan,
    universe,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(signals.router)
api_router.include_router(scanner.router)
api_router.include_router(charts.router)
api_router.include_router(market.router)
api_router.include_router(backtest.router)
api_router.include_router(ai.router)
api_router.include_router(notifications.router)
api_router.include_router(data.router)
api_router.include_router(exchanges.router)
api_router.include_router(pump_hunter.router)
api_router.include_router(trade_plan.router)
api_router.include_router(ml.router)
api_router.include_router(universe.router)
api_router.include_router(entry.router)
