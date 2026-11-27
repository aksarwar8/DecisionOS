"""Add isolated operational records; no changes to retail tables.

Revision ID: v3_0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "v3_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "decisionos_records",
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.Column("record_id", sa.String(128), primary_key=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_decisionos_records_kind_created", "decisionos_records", ["kind", "created_at"])


def downgrade():
    op.drop_index("ix_decisionos_records_kind_created", table_name="decisionos_records")
    op.drop_table("decisionos_records")
