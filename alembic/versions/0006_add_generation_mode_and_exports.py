"""Add task generation mode and generated exports."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "mode",
                sa.String(20),
                nullable=False,
                server_default="review",
            )
        )
    op.create_table(
        "exports",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("stored_name", sa.String(200), nullable=False),
        sa.Column("download_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
    )


def downgrade() -> None:
    op.drop_table("exports")
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("mode")
