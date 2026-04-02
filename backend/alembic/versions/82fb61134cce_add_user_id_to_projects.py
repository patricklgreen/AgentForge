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
    # Check if user_id column already exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'projects' AND column_name = 'user_id'
    """))
    
    if not result.fetchone():
        # Add user_id column to projects table only if it doesn't exist
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
    # Check if user_id column exists before trying to drop it
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'projects' AND column_name = 'user_id'
    """))
    
    if result.fetchone():
        # Remove user_id column from projects table only if it exists
        op.drop_column("projects", "user_id")