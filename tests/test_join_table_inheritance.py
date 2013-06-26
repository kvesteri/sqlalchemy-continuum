import sqlalchemy as sa
from sqlalchemy_continuum import Versioned
from tests import TestCase


class TestJoinTableInheritance(TestCase):
    def create_models(self):
        class TextItem(self.Model, Versioned):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
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
        self.BlogPost = BlogPost

    def test_each_class_has_distinct_history_class(self):
        TextItemHistory = self.TextItem.__versioned__['class']
        ArticleHistory = self.Article.__versioned__['class']
        BlogPostHistory = self.BlogPost.__versioned__['class']
        assert TextItemHistory.__table__.name == 'text_item_history'
        assert ArticleHistory.__table__.name == 'article_history'
        assert BlogPostHistory.__table__.name == 'blog_post_history'
        assert issubclass(ArticleHistory, TextItemHistory)
        assert issubclass(BlogPostHistory, TextItemHistory)

    def test_consecutive_insert_and_delete(self):
        article = self.Article()
        self.session.add(article)
        self.session.flush()
        self.session.delete(article)
        self.session.commit()
