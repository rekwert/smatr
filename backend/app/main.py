from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.ws import router as ws_router
from app.config.constants import DISCLAIMER
from app.config.settings import settings
from app.core.exceptions import setup_logging
from app.database.connection import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    try:
        await init_db()
    except Exception as exc:  # noqa: BLE001
        # Allow API boot without DB for engine-only / frontend mock usage
        import logging

        logging.getLogger(__name__).info(
            "Postgres unavailable — running without DB persistence (%s)", exc
        )
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    description="Smart Money AI Scanner — Bybit linear USDT perpetual analytics",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "exchange": "bybit",
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/v1/status")
async def api_status():
    return {
        "status": "ok",
        "locale": "ru",
        "exchanges": ["bybit", "okx", "bitget", "mexc", "bingx", "kucoin"],
        "mode": "confirmation",
        "disclaimer": "Только аналитика. Не финансовый совет.",
    }
