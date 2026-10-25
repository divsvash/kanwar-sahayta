"""
One-command demo runner.

Usage:
    pip install -r requirements-demo.txt
    python run_demo.py

Then open http://127.0.0.1:8000 - creates ./kanwar_demo.db (SQLite),
creates tables, seeds fake demo data on first run, and starts the app.
"""

import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./kanwar_demo.db")
os.environ.setdefault("DEBUG", "false")

import uvicorn  # noqa: E402

from app.core.database import engine, Base  # noqa: E402

# import every model so create_all sees all tables
import app.domain.platform.models  # noqa: E402,F401
import app.domain.identity.models  # noqa: E402,F401
import app.domain.journey.models  # noqa: E402,F401
import app.domain.safety.models  # noqa: E402,F401

from app.core.database import async_session_factory  # noqa: E402
from scripts.seed_demo import seed_if_empty  # noqa: E402


async def prepare() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        seeded = await seed_if_empty(session)
    print("Demo data seeded." if seeded else "Demo data already present, keeping it.")


if __name__ == "__main__":
    asyncio.run(prepare())
    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=8000)
