"""Add persistent analysis recovery attempts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "recovery_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.drop_column("recovery_attempts")
