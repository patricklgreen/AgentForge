"""add visual_references to projects

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-04-21

The column exists on the SQLAlchemy model but was never added via Alembic.
Without it, INSERTs fail with UndefinedColumnError (HTTP 500 on create project)
for databases that were migrated only through Alembic (create_all does not
ALTER existing tables to add new columns).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4e5f6a7b8c9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("projects")}
    if "visual_references" not in cols:
        op.add_column(
            "projects",
            sa.Column(
                "visual_references",
                postgresql.JSON(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("projects")}
    if "visual_references" in cols:
        op.drop_column("projects", "visual_references")
