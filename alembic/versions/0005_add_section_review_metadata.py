"""Add immutable section review revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "section_reviews",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("section_key", sa.String(80), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("editor", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "section_key", "revision"),
    )
    op.create_index(
        op.f("ix_section_reviews_task_id"), "section_reviews", ["task_id"], unique=False
    )
    op.create_index(
        op.f("ix_section_reviews_section_key"),
        "section_reviews",
        ["section_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_section_reviews_section_key"), table_name="section_reviews")
    op.drop_index(op.f("ix_section_reviews_task_id"), table_name="section_reviews")
    op.drop_table("section_reviews")
