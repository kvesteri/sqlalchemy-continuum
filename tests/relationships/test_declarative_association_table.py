import pytest
import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager

from tests import TestCase, create_test_cases


class DeclarativeAssociationTableTestCase(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        class ArticleTag(self.Model):
            __tablename__ = 'article_tag'
            __versioned__ = {}
            __table_args__ = (
                sa.UniqueConstraint('article_id', 'tag_id'),
            )

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            article_id = sa.Column(sa.Integer, sa.ForeignKey('article.id'))
            tag_id = sa.Column(sa.Integer, sa.ForeignKey('tag.id'))
            article = sa.orm.relationship('Article')
            tag = sa.orm.relationship('Tag')

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            articles = sa.orm.relationship(
                Article,
                secondary='article_tag',
            )

        self.Article = Article
        self.Tag = Tag
        self.ArticleTag = ArticleTag


    def test_create_association_table_from_other_tables(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        self.session.add(article)
        self.session.add(tag)
        self.session.commit()
        self.session.add(self.ArticleTag(article=article, tag=tag))
        self.session.commit()


create_test_cases(DeclarativeAssociationTableTestCase)
