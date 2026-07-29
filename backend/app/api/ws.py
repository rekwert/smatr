from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, select

from app.database.connection import SessionLocal
from app.database.models import Signal

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws/signals")
async def signals_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send latest snapshot
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(Signal)
                    .where(Signal.status == "active")
                    .order_by(desc(Signal.score))
                    .limit(20)
                )
            ).scalars().all()
            await websocket.send_json(
                {
                    "type": "snapshot",
                    "signals": [
                        {
                            "id": s.id,
                            "symbol": s.symbol,
                            "score": s.score,
                            "direction": s.direction,
                            "signal_type": s.signal_type,
                        }
                        for s in rows
                    ],
                }
            )

        while True:
            # Keepalive / allow client pings
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if raw == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
