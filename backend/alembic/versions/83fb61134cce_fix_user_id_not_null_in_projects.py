"""fix_user_id_not_null_in_projects

Revision ID: 83fb61134cce
Revises: 82fb61134cce
Create Date: 2026-03-30 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '83fb61134cce'
down_revision = '82fb61134cce'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix the user_id column in projects table to be NOT NULL.
    
    This migration:
    1. Deletes any existing projects without user_id (should be none with auth now)
    2. Makes user_id NOT NULL
    """
    
    # Delete any projects without user_id (there shouldn't be any with auth enabled)
    op.execute("DELETE FROM projects WHERE user_id IS NULL")
    
    # Make user_id NOT NULL
    op.alter_column(
        'projects', 
        'user_id',
        existing_type=postgresql.UUID(),
        nullable=False
    )


def downgrade() -> None:
    """Make user_id nullable again (for rollback purposes)."""
    op.alter_column(
        'projects', 
        'user_id',
        existing_type=postgresql.UUID(),
        nullable=True
    )