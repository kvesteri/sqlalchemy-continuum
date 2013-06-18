from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy_continuum.alembic import OperationsProxy
from tests import TestCase, QueryPool


class TestAlembicHelpers(TestCase):
    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.context = MigrationContext.configure(self.connection)
        self.op = OperationsProxy(Operations(self.context))

    def test_add_column(self):
        self.op.add_column(
            'article_history',
            sa.Column('some_added_column', sa.Unicode(255))
        )
        assert 'CREATE OR REPLACE FUNCTION' in QueryPool.queries[-1]
        assert 'NEW."some_added_column"' in QueryPool.queries[-1]

        assert 'DROP FUNCTION' in QueryPool.queries[-2]

    def test_drop_column(self):
        self.op.drop_column(
            'article_history',
            'name'
        )
        assert 'CREATE OR REPLACE FUNCTION' in QueryPool.queries[-1]
        assert 'NEW."name"' not in QueryPool.queries[-1]

        assert 'DROP FUNCTION' in QueryPool.queries[-2]

    def test_create_table(self):
        self.op.create_table(
            'some_table',
            sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
            sa.Column('name', sa.Unicode(255))
        )
        self.op.create_table(
            'some_table_history',
            sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
            sa.Column('name', sa.Unicode(255))
        )
        assert 'CREATE TRIGGER' in QueryPool.queries[-1]
        assert 'CREATE OR REPLACE FUNCTION' in QueryPool.queries[-2]

        self.op.drop_table('some_table_history')
        self.op.drop_table('some_table')

    def test_drop_table(self):
        self.op.create_table(
            'some_table',
            sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
            sa.Column('name', sa.Unicode(255))
        )
        self.op.create_table(
            'some_table_history',
            sa.Column('id', sa.Integer, autoincrement=True, primary_key=True),
            sa.Column('name', sa.Unicode(255))
        )
        self.op.drop_table('some_table_history')
        self.op.drop_table('some_table')
        assert 'DROP TABLE' in QueryPool.queries[-1]
        assert 'DROP TABLE' in QueryPool.queries[-2]
        assert 'DROP FUNCTION' in QueryPool.queries[-3]
