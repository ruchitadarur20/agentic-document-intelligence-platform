from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import entities  # noqa: F401


@pytest.mark.asyncio
async def test_upload_process_chat_history_end_to_end(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sample = b"Retention is seven years. AI answers must cite source chunks."
        upload = await client.post(
            "/documents/upload",
            files={"file": ("policy.txt", sample, "text/plain")},
        )
        assert upload.status_code == 200
        document_id = upload.json()["document_id"]

        process = await client.post(
            "/documents/process",
            json={"document_id": document_id, "force": True},
        )
        assert process.status_code == 200
        assert process.json()["chunk_count"] >= 1

        chat = await client.post("/chat", json={"query": "What is the retention requirement?"})
        assert chat.status_code == 200
        payload = chat.json()
        assert payload["citations"]
        assert payload["validation"]["supported"] is True

        history = await client.get("/history", params={"conversation_id": payload["conversation_id"]})
        assert history.status_code == 200
        assert [item["role"] for item in history.json()] == ["user", "assistant"]

    await engine.dispose()

