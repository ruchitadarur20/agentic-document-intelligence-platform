"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("storage_uri", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_checksum", "documents", ["checksum"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_trace_id", "runs", ["trace_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table(
        "embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("chunk_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index("ix_embeddings_doc_chunk", "embeddings", ["document_id", "chunk_id"])
    op.create_index("ix_embeddings_document_id", "embeddings", ["document_id"])
    op.create_index("ix_embeddings_chunk_id", "embeddings", ["chunk_id"])
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("relevance", sa.Integer(), nullable=False),
        sa.Column("faithfulness", sa.Integer(), nullable=False),
        sa.Column("completeness", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("token_usage", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_versions_name", "prompt_versions", ["name"])
    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("variant", sa.String(length=120), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiments_name", "experiments", ["name"])


def downgrade() -> None:
    for table in (
        "experiments",
        "prompt_versions",
        "evaluations",
        "embeddings",
        "messages",
        "runs",
        "documents",
        "conversations",
        "users",
    ):
        op.drop_table(table)

