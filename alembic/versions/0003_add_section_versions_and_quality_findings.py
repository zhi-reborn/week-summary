"""Add generated section versions and quality findings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "section_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("section_id", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "section_id", "version"),
    )
    op.create_index("ix_section_versions_task_id", "section_versions", ["task_id"])
    op.create_index("ix_section_versions_section_id", "section_versions", ["section_id"])
    op.create_table(
        "quality_findings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("section_version_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("token", sa.String(300), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_findings_task_id", "quality_findings", ["task_id"])
    op.create_index(
        "ix_quality_findings_section_version_id",
        "quality_findings",
        ["section_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_quality_findings_section_version_id", table_name="quality_findings")
    op.drop_index("ix_quality_findings_task_id", table_name="quality_findings")
    op.drop_table("quality_findings")
    op.drop_index("ix_section_versions_section_id", table_name="section_versions")
    op.drop_index("ix_section_versions_task_id", table_name="section_versions")
    op.drop_table("section_versions")
