"""Store teacher supplied source excerpts for grounded study material."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("class_outlines", sa.Column("source_text", sa.Text(), nullable=True))
    # Previous notes were generated without teacher-approved source text.
    op.execute("UPDATE class_outlines SET notes = NULL, study_plan = NULL, generated_by = NULL")


def downgrade():
    op.drop_column("class_outlines", "source_text")
