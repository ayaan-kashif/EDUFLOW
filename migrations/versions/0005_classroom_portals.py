"""Separate teacher/student accounts, enrollment, and published materials."""

import sqlalchemy as sa
from alembic import op

from app.domain.types import PortableJSON, PortableUUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_users",
        sa.Column("id", PortableUUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("enrollment_code", sa.String(16), unique=True),
    )
    op.create_index("ix_portal_users_email", "portal_users", ["email"], unique=True)
    op.create_table(
        "portal_sessions",
        sa.Column("id", PortableUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PortableUUID(as_uuid=True), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portal_sessions_user_id", "portal_sessions", ["user_id"])
    op.create_table(
        "teacher_enrollments",
        sa.Column("teacher_id", PortableUUID(as_uuid=True), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("student_id", PortableUUID(as_uuid=True), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "class_outlines",
        sa.Column("id", PortableUUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("teacher_id", PortableUUID(as_uuid=True), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("study_plan", PortableJSON()),
        sa.Column("generated_by", sa.String(200)),
    )
    op.create_index("ix_class_outlines_teacher_id", "class_outlines", ["teacher_id"])


def downgrade():
    op.drop_table("class_outlines")
    op.drop_table("teacher_enrollments")
    op.drop_table("portal_sessions")
    op.drop_table("portal_users")
