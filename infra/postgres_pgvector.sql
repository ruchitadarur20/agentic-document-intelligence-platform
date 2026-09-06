CREATE EXTENSION IF NOT EXISTS vector;

-- Production option: replace JSON vectors with pgvector for approximate nearest-neighbor search.
-- The app currently keeps JSON vectors for portability in local demos; use this pattern when
-- enabling native pgvector storage.
ALTER TABLE embeddings
  ADD COLUMN IF NOT EXISTS vector_native vector(384);

CREATE INDEX IF NOT EXISTS ix_embeddings_vector_native_hnsw
  ON embeddings
  USING hnsw (vector_native vector_cosine_ops);

CREATE INDEX IF NOT EXISTS ix_embeddings_metadata_gin
  ON embeddings
  USING gin (chunk_metadata);

