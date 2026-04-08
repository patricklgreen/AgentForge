"""Add LangGraph checkpoints table

Revision ID: 3fe8009adca6
Revises: c3a1465af2af
Create Date: 2026-04-08 17:55:13.184515

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3fe8009adca6'
down_revision = 'c3a1465af2af'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create LangGraph checkpoints table
    op.create_table(
        'checkpoints',
        sa.Column('thread_id', sa.String(), nullable=False),
        sa.Column('checkpoint_ns', sa.String(), nullable=False, default=''),
        sa.Column('checkpoint_id', sa.String(), nullable=False),
        sa.Column('parent_checkpoint_id', sa.String(), nullable=True),
        sa.Column('checkpoint', sa.LargeBinary(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False, default={}),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_ns', 'checkpoint_id')
    )
    
    # Create index for efficient queries
    op.create_index('ix_checkpoints_thread_id', 'checkpoints', ['thread_id'])


def downgrade() -> None:
    op.drop_index('ix_checkpoints_thread_id', 'checkpoints')
    op.drop_table('checkpoints')