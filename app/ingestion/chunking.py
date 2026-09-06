import re
from uuid import UUID

from app.core.config import settings


class TextChunker:
    def chunk(self, document_id: UUID, text: str, metadata: dict) -> list[dict]:
        cleaned = self._clean(text)
        chunks: list[dict] = []
        start = 0
        index = 0
        while start < len(cleaned):
            end = min(start + settings.chunk_size, len(cleaned))
            boundary = cleaned.rfind(" ", start, end)
            if boundary > start + 200:
                end = boundary
            piece = cleaned[start:end].strip()
            if piece:
                chunks.append(
                    {
                        "chunk_id": f"{document_id}:{index}",
                        "text": piece,
                        "metadata": {
                            **metadata,
                            "chunk_index": index,
                            "char_start": start,
                            "char_end": end,
                        },
                    }
                )
                index += 1
            if end >= len(cleaned):
                break
            start = max(end - settings.chunk_overlap, 0)
        return chunks

    def _clean(self, text: str) -> str:
        text = text.replace("\x00", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
