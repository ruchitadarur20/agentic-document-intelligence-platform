"""auth fields and pgvector production extension

Revision ID: 0002_auth_pgvector
Revises: 0001_initial
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_auth_pgvector"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("users", sa.Column("role", sa.String(length=40), nullable=False, server_default="analyst"))
    op.add_column("users", sa.Column("api_key_hash", sa.String(length=128), nullable=True))
    op.create_index("ix_users_role", "users", ["role"])
    op.create_unique_constraint("uq_users_api_key_hash", "users", ["api_key_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_users_api_key_hash", "users", type_="unique")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "api_key_hash")
    op.drop_column("users", "role")

