"""Add confirmed people, sourced facts, and resumable job steps."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("task_id", "id"),
    )
    op.create_table(
        "facts",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("id", sa.String(80), nullable=False),
        sa.Column("person_id", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("topic", sa.String(300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("task_id", "id"),
    )
    op.create_index("ix_facts_person_id", "facts", ["person_id"])
    op.create_index("ix_facts_kind", "facts", ["kind"])
    op.create_table(
        "fact_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("fact_id", sa.String(80), nullable=False),
        sa.Column("person_id", sa.String(20), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fact_sources_task_id", "fact_sources", ["task_id"])
    op.create_index("ix_fact_sources_fact_id", "fact_sources", ["fact_id"])
    op.create_table(
        "job_steps",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("step_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_job_steps_status",
        ),
        sa.UniqueConstraint("task_id", "step_type", "entity_id"),
    )
    op.create_index("ix_job_steps_task_id", "job_steps", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_job_steps_task_id", table_name="job_steps")
    op.drop_table("job_steps")
    op.drop_index("ix_fact_sources_fact_id", table_name="fact_sources")
    op.drop_index("ix_fact_sources_task_id", table_name="fact_sources")
    op.drop_table("fact_sources")
    op.drop_index("ix_facts_kind", table_name="facts")
    op.drop_index("ix_facts_person_id", table_name="facts")
    op.drop_table("facts")
    op.drop_table("people")
