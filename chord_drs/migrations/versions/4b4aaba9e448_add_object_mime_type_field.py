"""add object mime_type field

Revision ID: 4b4aaba9e448
Revises: 5e982af5cde4
Create Date: 2024-10-28 16:27:17.598861

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b4aaba9e448'
down_revision = '5e982af5cde4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('drs_object', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mime_type', sa.String(length=128), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('drs_object', schema=None) as batch_op:
        batch_op.drop_column('mime_type')

    # ### end Alembic commands ###
