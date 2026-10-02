"""Source extraction reuse and reviewed recovery scenarios."""

import sqlalchemy as sa
from alembic import op

from app.domain.types import PortableJSON, PortableUUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_curricula",
        sa.Column(
            "document_id",
            PortableUUID(as_uuid=True),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("node_ids", PortableJSON(), nullable=False),
        sa.Column("metadata_json", PortableJSON(), nullable=False),
    )
    op.create_table(
        "recovery_scenarios",
        sa.Column("id", PortableUUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "plan_id", PortableUUID(as_uuid=True), sa.ForeignKey("plan_versions.id"), nullable=False
        ),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("payload", PortableJSON(), nullable=False),
        sa.Column("applied_plan_id", PortableUUID(as_uuid=True), sa.ForeignKey("plan_versions.id")),
        sa.Column("applied_option", sa.String()),
    )
    op.create_index("ix_recovery_scenarios_plan_id", "recovery_scenarios", ["plan_id"])


def downgrade():
    op.drop_table("recovery_scenarios")
    op.drop_table("source_curricula")
