import sqlalchemy as sa
from pytest import raises, skip
from sqlalchemy.orm import declarative_base

from sqlalchemy_continuum import (
    ImproperlyConfigured,
    TransactionFactory,
    versioning_manager,
)
from tests import TestCase


class TestVersionedModelWithoutVersioning(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {'versioning': False}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.TextItem = TextItem

    def test_does_not_create_history_class(self):
        assert 'class' not in self.TextItem.__versioned__

    def test_does_not_create_history_table(self):
        assert 'text_item_history' not in self.Model.metadata.tables

    def test_does_add_objects_to_unit_of_work(self):
        self.session.add(self.TextItem())
        self.session.commit()


class TestWithUnknownUserClass:
    def test_raises_improperly_configured_error(self):
        self.Model = declarative_base()

        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.TextItem = TextItem

        versioning_manager.user_cls = 'User'
        versioning_manager.declarative_base = self.Model

        factory = TransactionFactory()
        with raises(ImproperlyConfigured):
            factory(versioning_manager)


class TestWithCreateModelsAsFalse(TestCase):
    should_create_models = False

    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        class Category(self.Model):
            __tablename__ = 'category'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(
                Article, backref=sa.orm.backref('category', uselist=False)
            )

        self.Article = Article
        self.Category = Category

    def test_does_not_create_models(self):
        assert 'class' not in self.Article.__versioned__

    def test_insert(self):
        if self.options['native_versioning'] is False:
            skip()
        article = self.Article(name='Some article')
        self.session.add(article)
        self.session.commit()

        version = self.session.execute(
            sa.text('SELECT * FROM article_version')
        ).fetchone()
        assert version.transaction_id > 0
        assert version.id == article.id
        assert version.name == 'Some article'


class TestWithoutAnyVersionedModels(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        self.Article = Article

    def test_insert(self):
        article = self.Article(name='Some article')
        self.session.add(article)
        self.session.commit()
