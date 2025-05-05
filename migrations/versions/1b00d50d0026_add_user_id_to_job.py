"""Add user_id to Job

Revision ID: 1b00d50d0026
Revises: 
Create Date: 2025-05-05 02:43:50.123456

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1b00d50d0026'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False, server_default='1'))  # Устанавливаем значение по умолчанию
        batch_op.create_foreign_key(
            'fk_job_user_id',
            'user',
            ['user_id'],
            ['id']
        )

def downgrade():
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_constraint('fk_job_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')