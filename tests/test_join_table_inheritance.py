import sqlalchemy as sa
from sqlalchemy_continuum import Versioned
from tests import TestCase


class TestJoinTableInheritance(TestCase):
    def create_models(self):
        class TextItem(self.Model, Versioned):
            __tablename__ = 'text_item'

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            discriminator = sa.Column(
                sa.Unicode(100)
            )

            __mapper_args__ = {
                'polymorphic_on': discriminator,
            }

        class Article(TextItem):
            __tablename__ = 'article'
            __mapper_args__ = {'polymorphic_identity': u'article'}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(TextItem.id),
                autoincrement=True, primary_key=True
            )

        class BlogPost(TextItem):
            __tablename__ = 'blog_post'
            __mapper_args__ = {'polymorphic_identity': u'blog_post'}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(TextItem.id),
                autoincrement=True, primary_key=True
            )

        self.TextItem = TextItem
        self.Article = Article

    def test_each_class_has_distinct_translation_class(self):
        class_ = self.TextItem.__versioned__['class']
        assert class_.__name__ == 'TextItemHistory'
        class_ = self.Article.__versioned__['class']
        assert class_.__name__ == 'ArticleHistory'
