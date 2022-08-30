from copy import copy
from pytest import raises
import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager
from sqlalchemy_continuum.exc import ClassNotVersioned
from sqlalchemy_continuum.utils import get_versioning_manager

from tests import TestCase


class TestGetVersioningManager(TestCase):
    def create_models(self):
        """
        Creates many-to-many relationship between Article and Tag
        Article is versioned. But Tag is not versioned
        """
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = copy(self.options)

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

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            articles = sa.orm.relationship(Article, secondary=article_tag, backref='tags')

        self.Article = Article
        self.article_tag = article_tag
        self.Tag = Tag

    def test_parent_class(self):
        assert get_versioning_manager(self.Article) == versioning_manager

    def test_parent_table(self):
        assert get_versioning_manager(self.Article.__table__) == versioning_manager

    def test_version_class(self):
        assert get_versioning_manager(self.ArticleVersion) == versioning_manager

    def test_version_table(self):
        assert get_versioning_manager(self.ArticleVersion.__table__) == versioning_manager

    def test_association_table(self):
        assert get_versioning_manager(self.article_tag) == versioning_manager

    def test_aliased_class(self):
        assert get_versioning_manager(sa.orm.aliased(self.Article)) == versioning_manager
        assert get_versioning_manager(sa.orm.aliased(self.ArticleVersion)) == versioning_manager

    def test_unknown_class(self):
        with raises(ClassNotVersioned):
            get_versioning_manager(self.Tag)
