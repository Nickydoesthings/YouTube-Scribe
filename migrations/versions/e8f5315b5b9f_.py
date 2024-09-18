"""empty message

Revision ID: e8f5315b5b9f
Revises: fc8777ae687a
Create Date: 2024-09-18 18:06:52.349257

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8f5315b5b9f'
down_revision = 'fc8777ae687a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_confirmed', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('confirmation_token', sa.String(length=100), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('confirmation_token')
        batch_op.drop_column('is_confirmed')

    # ### end Alembic commands ###
