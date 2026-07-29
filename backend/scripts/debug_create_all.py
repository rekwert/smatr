import asyncio
from sqlalchemy import text, inspect
from app.database.connection import engine, Base
from app.database import models  # noqa: F401


async def main() -> None:
    print("meta", len(Base.metadata.tables))

    async with engine.begin() as conn:

        def _create(sync_conn):
            Base.metadata.create_all(sync_conn)
            insp = inspect(sync_conn)
            print("insp", insp.get_table_names())

        await conn.run_sync(_create)

    async with engine.connect() as c:
        r = await c.execute(
            text("select tablename from pg_tables where schemaname='public' order by 1")
        )
        rows = [x[0] for x in r.fetchall()]
        print("pg_tables", len(rows), rows)


if __name__ == "__main__":
    asyncio.run(main())
