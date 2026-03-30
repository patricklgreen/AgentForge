"""add_user_id_to_projects

Revision ID: 82fb61134cce
Revises: 641bf38661c2
Create Date: 2026-03-30 21:46:17.659352

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '82fb61134cce'
down_revision = '641bf38661c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id column to projects table
    op.add_column(
        "projects",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,  # Allow NULL initially for existing projects
        ),
    )


def downgrade() -> None:
    # Remove user_id column from projects table
    op.drop_column("projects", "user_id")