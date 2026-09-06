import hashlib
import re
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ingestion.chunking import TextChunker
from app.ingestion.parsers import DocumentParser
from app.models.entities import Document
from app.observability.metrics import DOCUMENTS_PROCESSED
from app.services.llm import LLMClient
from app.services.metadata_store import MetadataStore
from app.services.vector_store import VectorStore


class DocumentIngestionPipeline:
    def __init__(self) -> None:
        self.parser = DocumentParser()
        self.chunker = TextChunker()
        self.llm = LLMClient()
        self.vector_store = VectorStore()
        self.metadata_store = MetadataStore()

    async def upload(self, session: AsyncSession, file: UploadFile) -> Document:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        document_id = uuid.uuid4()
        safe_filename = Path(file.filename or str(document_id)).name
        destination = settings.upload_dir / f"{document_id}_{safe_filename}"
        with destination.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
        document = Document(
            id=document_id,
            filename=safe_filename,
            content_type=file.content_type or "application/octet-stream",
            storage_uri=str(destination),
            checksum=checksum,
            status="uploaded",
            metadata_json={"size_bytes": destination.stat().st_size},
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        await self.metadata_store.save_raw_document_metadata(
            document.id,
            {
                "filename": document.filename,
                "content_type": document.content_type,
                "checksum": document.checksum,
                "storage_uri": document.storage_uri,
                **document.metadata_json,
            },
        )
        return document

    async def upload_path(
        self, session: AsyncSession, source: Path, content_type: str = "text/plain"
    ) -> Document:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        document_id = uuid.uuid4()
        safe_filename = source.name
        destination = settings.upload_dir / f"{document_id}_{safe_filename}"
        shutil.copyfile(source, destination)
        checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
        document = Document(
            id=document_id,
            filename=safe_filename,
            content_type=content_type,
            storage_uri=str(destination),
            checksum=checksum,
            status="uploaded",
            metadata_json={"size_bytes": destination.stat().st_size, "demo_case": True},
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        await self.metadata_store.save_raw_document_metadata(
            document.id,
            {
                "filename": document.filename,
                "content_type": document.content_type,
                "checksum": document.checksum,
                "storage_uri": document.storage_uri,
                **document.metadata_json,
            },
        )
        return document

    async def process(self, session: AsyncSession, document: Document, force: bool = False) -> int:
        if document.status == "processed" and not force:
            return 0
        text, metadata = self.parser.parse(Path(document.storage_uri), document.content_type)
        metadata = {
            **document.metadata_json,
            **metadata,
            "document_id": str(document.id),
            "filename": document.filename,
            **self._governance_metadata(document.filename, text),
        }
        chunks = self.chunker.chunk(document.id, text, metadata)
        vectors = self.llm.embed_documents([chunk["text"] for chunk in chunks])
        await self.metadata_store.save_chunk_metadata(document.id, chunks)
        await self.vector_store.delete_document_chunks(session, document.id)
        await self.vector_store.add_chunks(
            session,
            document.id,
            chunks,
            vectors,
            settings.azure_openai_embedding_deployment,
        )
        document.status = "processed"
        document.page_count = int(metadata.get("page_count", 0) or 0)
        document.metadata_json = metadata
        await session.commit()
        DOCUMENTS_PROCESSED.labels(status="processed").inc()
        return len(chunks)

    def _governance_metadata(self, filename: str, text: str) -> dict[str, object]:
        content = f"{filename} {text}".lower()
        if any(term in content for term in ("vendor", "third-party", "soc 2")):
            classification = "vendor risk"
        elif any(term in content for term in ("incident", "exposure", "containment")):
            classification = "incident"
        elif any(term in content for term in ("employee", "onboarding", "contractor")):
            classification = "hr"
        elif any(term in content for term in ("loan", "borrower", "underwriting")):
            classification = "loan"
        elif any(term in content for term in ("confidential", "security", "encryption")):
            classification = "confidential policy"
        else:
            classification = "general document"

        flags = []
        flag_terms = {
            "confidential data": ("confidential", "customer data", "personal financial"),
            "retention rule": ("retained", "retention", "years"),
            "citation required": ("cite", "citation", "source document chunks"),
            "human review": ("manual review", "human review", "human validation"),
            "loan document": ("loan", "borrower", "underwriting"),
            "tax/financial record": ("tax", "financial statement", "account number"),
        }
        for label, terms in flag_terms.items():
            if any(term in content for term in terms):
                flags.append(label)
        if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
            flags.append("possible ssn")
        if re.search(r"\b\d{9,16}\b", text):
            flags.append("possible account number")

        return {
            "classification": classification,
            "compliance_flags": sorted(set(flags)),
        }
