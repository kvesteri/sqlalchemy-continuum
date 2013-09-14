import sqlalchemy as sa
from sqlalchemy_continuum import VersioningStrategy
from tests import TestCase


class TestValidityStrategy(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, ),
                'strategy': VersioningStrategy.VALIDITY
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

        self.TextItem = TextItem

    def test_schema_contains_end_transaction_id(self):
        table = self.TextItem.__versioned__['class'].__table__
        assert 'end_transaction_id' in table.c
        table.c.end_transaction_id
        assert table.c.end_transaction_id.nullable
        assert not table.c.end_transaction_id.primary_key


class TestJoinTableInheritanceWithValidityVersioning(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, ),
                'strategy': VersioningStrategy.VALIDITY
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

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.TextItemHistory = self.TextItem.__versioned__['class']
        self.ArticleHistory = self.Article.__versioned__['class']
        self.BlogPostHistory = self.BlogPost.__versioned__['class']

    def test_all_tables_contain_transaction_id_column(self):
        assert 'end_transaction_id' in self.TextItemHistory.__table__.c
        assert 'end_transaction_id' in self.ArticleHistory.__table__.c
        assert 'end_transaction_id' in self.BlogPostHistory.__table__.c
