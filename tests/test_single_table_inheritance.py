from pytest import mark
import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager, version_class
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

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.TextItemHistory = version_class(self.TextItem)
        self.ArticleHistory = version_class(self.Article)
        self.BlogPostHistory = version_class(self.BlogPost)

    def test_version_class_map(self):
        manager = self.TextItem.__versioning_manager__
        assert len(manager.version_class_map.keys()) == 3

    def test_transaction_log_relations(self):
        tx_log = versioning_manager.transaction_log_cls
        assert tx_log.text_items
        assert tx_log.articles
        assert tx_log.blog_posts

    def test_each_class_has_distinct_version_class(self):
        assert self.TextItemHistory.__table__.name == 'text_item_version'
        assert self.ArticleHistory.__table__.name == 'text_item_version'
        assert self.BlogPostHistory.__table__.name == 'text_item_version'
        assert issubclass(self.ArticleHistory, self.TextItemHistory)
        assert issubclass(self.BlogPostHistory, self.TextItemHistory)

    @mark.skipif('True')
    def test_each_object_has_distinct_version_class(self):
        article = self.Article()
        blogpost = self.BlogPost()
        textitem = self.TextItem()

        self.session.add(article)
        self.session.add(blogpost)
        self.session.add(textitem)
        self.session.commit()

        assert type(textitem.versions[0]) == self.TextItemHistory
        assert type(article.versions[0]) == self.ArticleHistory
        assert type(blogpost.versions[0]) == self.BlogPostHistory

    def test_transaction_log_changed_entities(self):
        article = self.Article()
        article.name = u'Text 1'
        self.session.add(article)
        self.session.commit()
        TransactionLog = versioning_manager.transaction_log_cls
        transaction = (
            self.session.query(TransactionLog)
            .order_by(sa.sql.expression.desc(TransactionLog.issued_at))
        ).first()
        assert transaction.entity_names == [u'Article']
        assert transaction.changed_entities
