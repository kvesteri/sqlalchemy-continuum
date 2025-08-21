import sqlalchemy as sa
from packaging import version as py_pkg_version
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from tests import TestCase, create_test_cases


class AssociationTableRelationshipsTestCase(TestCase):
    def create_models(self):
        super().create_models()

        class PublishedArticle(self.Model):
            __tablename__ = 'published_article'
            __table_args__ = (
                PrimaryKeyConstraint('article_id', 'author_id'),
                {'keep_existing': True},
            )

            article_id = sa.Column(sa.Integer, sa.ForeignKey('article.id'))
            author_id = sa.Column(sa.Integer, sa.ForeignKey('author.id'))
            relationship_kwargs = {}
            if py_pkg_version.parse(sa.__version__) >= py_pkg_version.parse('1.4.0'):
                relationship_kwargs.update({'overlaps': 'articles'})
            author = relationship('Author', **relationship_kwargs)
            article = relationship('Article', **relationship_kwargs)

        self.PublishedArticle = PublishedArticle

        published_articles_table = sa.Table(
            PublishedArticle.__tablename__,
            PublishedArticle.metadata,
            extend_existing=True,
        )

        class Author(self.Model):
            __tablename__ = 'author'
            __versioned__ = {'base_classes': (self.Model,)}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            articles = relationship('Article', secondary=published_articles_table)

        self.Author = Author

    def test_version_relations(self):
        article = self.Article()
        name = 'Some article'
        article.name = name
        article.content = 'Some content'
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].name == name

        au = self.Author(name='Some author')
        self.session.add(au)
        self.session.commit()

        pa = self.PublishedArticle(article_id=article.id, author_id=au.id)
        self.session.add(pa)

        self.session.commit()


create_test_cases(AssociationTableRelationshipsTestCase)
