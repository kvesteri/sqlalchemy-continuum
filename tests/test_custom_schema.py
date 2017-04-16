import os
import sqlalchemy as sa
from six import PY3
from pytest import mark
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_continuum import (
    ClassNotVersioned,
    version_class,
    make_versioned,
    versioning_manager,
)
from tests import TestCase, get_driver_name, get_dns_from_driver


@mark.skipif("os.environ.get('DB') == 'sqlite'")
class TestCustomSchema(TestCase):
    def create_models(self):
        self.Model = declarative_base(metadata=sa.MetaData(schema='continuum'))

        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        article_tag = sa.Table(
            'article_tag',
            self.Model.metadata,
            sa.Column(
                'article_id',
                sa.Integer,
                sa.ForeignKey('article.id', ondelete='CASCADE'),
                primary_key=True,
            ),
            sa.Column(
                'tag_id',
                sa.Integer,
                sa.ForeignKey('tag.id', ondelete='CASCADE'),
                primary_key=True
            )
        )

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        Tag.articles = sa.orm.relationship(
            Article,
            secondary=article_tag,
            backref='tags'
        )

        self.Article = Article
        self.Tag = Tag

    def create_tables(self):
        self.connection.execute('DROP SCHEMA IF EXISTS continuum')
        self.connection.execute('CREATE SCHEMA continuum')
        TestCase.create_tables(self)

    def test_version_relations(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tags == []


@mark.skipif("os.environ.get('DB') == 'sqlite'")
class TestCustomVersionSchema(TestCase):
    def setup_method(self, method):
        self.Model = declarative_base(metadata=sa.MetaData(schema='continuum'))

        options = self.options
        options['table_schema'] = 'continuum_versions'
        make_versioned(options=options)

        driver = os.environ.get('DB', 'sqlite')
        self.driver = get_driver_name(driver)
        versioning_manager.plugins = self.plugins
        versioning_manager.transaction_cls = self.transaction_cls
        versioning_manager.user_cls = self.user_cls

        self.engine = create_engine(get_dns_from_driver(self.driver))
        # self.engine.echo = True
        self.create_models()

        sa.orm.configure_mappers()

        self.connection = self.engine.connect()

        if hasattr(self, 'Article'):
            try:
                self.ArticleVersion = version_class(self.Article)
            except ClassNotVersioned:
                pass
        if hasattr(self, 'Tag'):
            try:
                self.TagVersion = version_class(self.Tag)
            except ClassNotVersioned:
                pass
        self.create_tables()

        Session = sessionmaker(bind=self.connection)
        self.session = Session(autoflush=False)
        if driver == 'postgres-native':
            self.session.execute('CREATE EXTENSION IF NOT EXISTS hstore')

    def teardown_method(self, method):
        super(TestCustomVersionSchema, self).teardown_method(method)
        versioning_manager.options['table_schema'] = None

    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        article_tag = sa.Table(
            'article_tag',
            self.Model.metadata,
            sa.Column(
                'article_id',
                sa.Integer,
                sa.ForeignKey('article.id', ondelete='CASCADE'),
                primary_key=True,
            ),
            sa.Column(
                'tag_id',
                sa.Integer,
                sa.ForeignKey('tag.id', ondelete='CASCADE'),
                primary_key=True
            )
        )

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        Tag.articles = sa.orm.relationship(
            Article,
            secondary=article_tag,
            backref='tags'
        )

        self.Article = Article
        self.Tag = Tag

    def create_tables(self):
        self.connection.execute('DROP SCHEMA IF EXISTS continuum')
        self.connection.execute('CREATE SCHEMA continuum')
        self.connection.execute('DROP SCHEMA IF EXISTS continuum_versions')
        self.connection.execute('CREATE SCHEMA continuum_versions')
        TestCase.create_tables(self)

    def test_version_relations(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tags == []
