from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.ingestion.pipeline import DocumentIngestionPipeline
from app.models.entities import Document


async def process_document_task(session: AsyncSession, document_id: UUID, force: bool = False) -> int:
    document = await session.get(Document, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")
    return await DocumentIngestionPipeline().process(session, document, force)


async def process_document_background(document_id: UUID, force: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        await process_document_task(session, document_id, force)
