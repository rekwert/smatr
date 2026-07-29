import asyncio
from sqlalchemy import text
from app.database.connection import init_db, engine


async def main() -> None:
    try:
        await init_db()
        print("init_ok")
    except Exception as e:  # noqa: BLE001
        print("init_fail", type(e).__name__, e)
    async with engine.connect() as c:
        db = (await c.execute(text("select current_database(), current_user"))).fetchone()
        print("conn", db)
        n = (
            await c.execute(
                text("select count(*) from information_schema.tables where table_schema='public'")
            )
        ).scalar()
        print("tables", n)


if __name__ == "__main__":
    asyncio.run(main())
