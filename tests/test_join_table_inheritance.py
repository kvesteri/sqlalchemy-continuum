import sqlalchemy as sa
from tests import TestCase


class TestJoinTableInheritance(TestCase):
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

    def test_each_class_has_distinct_history_class(self):
        assert self.TextItemHistory.__table__.name == 'text_item_history'
        assert self.ArticleHistory.__table__.name == 'article_history'
        assert self.BlogPostHistory.__table__.name == 'blog_post_history'
        assert issubclass(self.ArticleHistory, self.TextItemHistory)
        assert issubclass(self.BlogPostHistory, self.TextItemHistory)

    def test_all_tables_contain_transaction_id_column(self):
        assert 'transaction_id' in self.TextItemHistory.__table__.c
        assert 'transaction_id' in self.ArticleHistory.__table__.c
        assert 'transaction_id' in self.BlogPostHistory.__table__.c

    def test_consecutive_insert_and_delete(self):
        article = self.Article()
        self.session.add(article)
        self.session.flush()
        self.session.delete(article)
        self.session.commit()

    def test_assign_transaction_id_to_both_parent_and_child_tables(self):
        article = self.Article()
        self.session.add(article)
        self.session.commit()
        assert self.session.execute(
            'SELECT transaction_id FROM article_history'
        ).fetchone()[0] == 1
        assert self.session.execute(
            'SELECT transaction_id FROM text_item_history'
        ).fetchone()[0] == 1

    def test_primary_keys(self):
        table = self.TextItemHistory.__table__
        assert len(table.primary_key.columns)
        assert 'id' in table.primary_key.columns
        assert 'transaction_id' in table.primary_key.columns
        table = self.ArticleHistory.__table__
        assert len(table.primary_key.columns)
        assert 'id' in table.primary_key.columns
        assert 'transaction_id' in table.primary_key.columns
