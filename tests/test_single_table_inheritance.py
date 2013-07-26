import sqlalchemy as sa
from tests import TestCase


class TestSingleTableInheritance(TestCase):
    def create_models(self):
        class TextItem(self.Model):
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
            __mapper_args__ = {'polymorphic_identity': u'article'}
            name = sa.Column(sa.Unicode(255))

        class BlogPost(TextItem):
            __mapper_args__ = {'polymorphic_identity': u'blog_post'}
            title = sa.Column(sa.Unicode(255))

        self.TextItem = TextItem
        self.Article = Article
        self.BlogPost = BlogPost

    def test_each_class_has_distinct_history_class(self):
        TextItemHistory = self.TextItem.__versioned__['class']
        ArticleHistory = self.Article.__versioned__['class']
        BlogPostHistory = self.BlogPost.__versioned__['class']
        assert TextItemHistory.__table__.name == 'text_item_history'
        assert ArticleHistory.__table__.name == 'text_item_history'
        assert BlogPostHistory.__table__.name == 'text_item_history'
        assert issubclass(ArticleHistory, TextItemHistory)
        assert issubclass(BlogPostHistory, TextItemHistory)

    def test_transaction_log(self):
        b = self.Article()
        b.name = u'Text 1'
        self.session.add(b)
        self.session.commit()

        options = self.TextItem.__versioned__
        TransactionLog = options['transaction_log']
        transaction = (
            self.session.query(TransactionLog)
            .order_by(sa.sql.expression.desc(TransactionLog.issued_at))
        ).first()
        assert transaction.entity_names == [u'Article']
        assert self.Article in transaction.changed_entities
