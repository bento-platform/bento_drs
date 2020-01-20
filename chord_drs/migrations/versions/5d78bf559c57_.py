"""empty message

Revision ID: 5d78bf559c57
Revises: 
Create Date: 2020-01-20 12:24:07.213738

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d78bf559c57'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('drs_bundle',
    sa.Column('created', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('checksum', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('parent_bundle_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['parent_bundle_id'], ['drs_bundle.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('drs_object',
    sa.Column('created', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('checksum', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=True),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('bundle_id', sa.Integer(), nullable=True),
    sa.Column('location', sa.String(length=500), nullable=False),
    sa.ForeignKeyConstraint(['bundle_id'], ['drs_bundle.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('drs_object')
    op.drop_table('drs_bundle')
    # ### end Alembic commands ###
