"""add memories table

Revision ID: 6d668d9fe779
Revises: 82e0397c1ded
Create Date: 2026-08-10 19:42:50.577481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6d668d9fe779'
down_revision: Union[str, Sequence[str], None] = '82e0397c1ded'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# NOTE: autogenerate also proposed dropping the checkpoint_* tables (checkpoints,
# checkpoint_writes, checkpoint_blobs, checkpoint_migrations) because they're owned/managed by
# langgraph-checkpoint-postgres's own PostgresSaver.setup(), not by our SQLAlchemy models. Left
# out deliberately -- Alembic must never touch LangGraph's own tables.


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('memories',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('task_id', sa.String(length=36), nullable=True),
    sa.Column('user_id', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('importance_score', sa.Float(), nullable=False),
    sa.Column('access_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('memories')
