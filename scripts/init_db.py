import asyncio

from app.db.init_db import initialize_database
from app.db.session import engine


async def main() -> None:
    await initialize_database(engine)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

