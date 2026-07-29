# Discord stub
from __future__ import annotations


async def send_discord(webhook_url: str, content: str) -> bool:
    if not webhook_url:
        return False
    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(webhook_url, json={"content": content})
    return resp.status_code in (200, 204)
