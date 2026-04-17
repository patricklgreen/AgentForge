"""add cost_summary to project_runs

Revision ID: a1b2c3d4e5f6
Revises: 83fb61134cce
Create Date: 2026-04-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a1b2c3d4e5f6"
down_revision = "83fb61134cce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_runs",
        sa.Column("cost_summary", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_runs", "cost_summary")
