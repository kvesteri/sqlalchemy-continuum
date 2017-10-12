from copy import copy
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase
from pytest import mark


class TestTableBuilder(TestCase):
    def test_assigns_foreign_keys_for_versions(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        cls = version_class(self.Tag)
        version = self.session.query(cls).first()
        assert version.name == u'some tag'
        assert version.id == 1
        assert version.article_id == 1

    def test_versioned_table_structure(self):
        table = version_class(self.Article).__table__
        assert 'id' in table.c
        assert 'name' in table.c
        assert 'content' in table.c
        assert 'description'in table.c
        assert 'transaction_id' in table.c
        assert 'operation_type' in table.c

    def test_removes_autoincrementation(self):
        table = version_class(self.Article).__table__
        assert table.c.id.autoincrement is False

    def test_removes_not_null_constraints(self):
        assert self.Article.__table__.c.name.nullable is False
        table = version_class(self.Article).__table__
        assert table.c.name.nullable is True

    def test_primary_keys_remain_not_nullable(self):
        assert self.Article.__table__.c.name.nullable is False
        table = version_class(self.Article).__table__
        assert table.c.id.nullable is False

    def test_transaction_id_column_not_nullable(self):
        assert self.Article.__table__.c.name.nullable is False
        table = version_class(self.Article).__table__
        assert table.c.transaction_id.nullable is False


class TestTableBuilderWithOnUpdate(TestCase):
    def create_models(self):
        options = copy(self.options)
        options['include'] = ['last_update', ]

        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = options

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            last_update = sa.Column(
                sa.DateTime,
                default=datetime.utcnow,
                onupdate=datetime.utcnow,
                nullable=False
            )
        self.Article = Article

    def test_takes_out_onupdate_triggers(self):
        table = version_class(self.Article).__table__
        assert table.c.last_update.onupdate is None

@mark.skipif("os.environ.get('DB') == 'sqlite'")
class TestTableBuilderInOtherSchema(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = copy(self.options)
            __table_args__ = {'schema': 'other'}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            last_update = sa.Column(
                sa.DateTime,
                default=datetime.utcnow,
                onupdate=datetime.utcnow,
                nullable=False
            )
        self.Article = Article

    def create_tables(self):
        self.connection.execute('DROP SCHEMA IF EXISTS other')
        self.connection.execute('CREATE SCHEMA other')
        TestCase.create_tables(self)

    def test_created_tables_retain_schema(self):
        table = version_class(self.Article).__table__
        assert table.schema is not None
        assert table.schema == self.Article.__table__.schema

