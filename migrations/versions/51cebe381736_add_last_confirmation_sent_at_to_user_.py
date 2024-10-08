"""Add last_confirmation_sent_at to User to rate limit email verification resend

Revision ID: 51cebe381736
Revises: e8f5315b5b9f
Create Date: 2024-09-19 12:33:06.963096

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '51cebe381736'
down_revision = 'e8f5315b5b9f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_confirmation_sent_at', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_confirmation_sent_at')

    # ### end Alembic commands ###
