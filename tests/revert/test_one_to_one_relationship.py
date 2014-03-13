from copy import copy
from tests import TestCase
import sqlalchemy as sa


class TestRevertOneToOneRelationship(TestCase):
    def create_models(self):
        class Category(self.Model):
            __tablename__ = 'category'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)
            category_id = sa.Column(sa.Integer, sa.ForeignKey(Category.id))
            category = sa.orm.relationship(
                Category,
                backref=sa.orm.backref(
                    'article',
                    uselist=False
                )
            )

        self.Article = Article
        self.Category = Category

    def test_revert_relationship(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        category = self.Category(name=u'some category')
        article.category = category
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].category == category.versions[0]
        article.category = None
        self.session.commit()
        self.session.refresh(article)
        assert article.category is None
        article.versions[0].revert(relations=['category'])
        self.session.commit()

        assert article.category == category
        assert article.category.name == u'some category'
