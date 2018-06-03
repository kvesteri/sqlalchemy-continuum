import sqlalchemy as sa
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from tests import TestCase, create_test_cases


class AssociationTableRelationshipsTestCase(TestCase):
    def create_models(self):
        super(AssociationTableRelationshipsTestCase, self).create_models()

        class PublishedArticle(self.Model):
            __tablename__ = 'published_article'
            __table_args__ = (
                PrimaryKeyConstraint("article_id", "author_id"),
                {'useexisting': True}
            )

            article_id = sa.Column(sa.Integer, sa.ForeignKey('article.id'))
            author_id = sa.Column(sa.Integer, sa.ForeignKey('author.id'))
            author = relationship('Author')
            article = relationship('Article')

        self.PublishedArticle = PublishedArticle

        published_articles_table = sa.Table(PublishedArticle.__tablename__,
                                            PublishedArticle.metadata,
                                            extend_existing=True)

        class Author(self.Model):
            __tablename__ = 'author'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            articles = relationship('Article', secondary=published_articles_table)

        self.Author = Author

    def test_version_relations(self):
        article = self.Article()
        name = u'Some article'
        article.name = name
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].name == name

        au = self.Author(name=u'Some author')
        self.session.add(au)
        self.session.commit()

        pa = self.PublishedArticle(article_id=article.id, author_id=au.id)
        self.session.add(pa)

        self.session.commit()



create_test_cases(AssociationTableRelationshipsTestCase)
