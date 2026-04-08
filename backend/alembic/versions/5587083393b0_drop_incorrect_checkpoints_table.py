"""Drop incorrect checkpoints table

Revision ID: 5587083393b0
Revises: 3fe8009adca6
Create Date: 2026-04-08 17:57:43.212305

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5587083393b0'
down_revision = '3fe8009adca6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the incorrect checkpoints table we created
    op.drop_index('ix_checkpoints_thread_id', 'checkpoints')
    op.drop_table('checkpoints')


def downgrade() -> None:
    # Recreate the old incorrect table if needed (but this shouldn't be used)
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
    op.create_index('ix_checkpoints_thread_id', 'checkpoints', ['thread_id'])