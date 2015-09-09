import pytest
import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase, uses_native_versioning, create_test_cases


class JoinTableInheritanceTestCase(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

            discriminator = sa.Column(
                sa.Unicode(100)
            )

            __mapper_args__ = {
                'polymorphic_on': discriminator,
                'with_polymorphic': '*'
            }

        class Article(TextItem):
            __tablename__ = 'article'
            __mapper_args__ = {'polymorphic_identity': u'article'}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(TextItem.id),
                primary_key=True
            )

        class BlogPost(TextItem):
            __tablename__ = 'blog_post'
            __mapper_args__ = {'polymorphic_identity': u'blog_post'}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(TextItem.id),
                primary_key=True
            )

        self.TextItem = TextItem
        self.Article = Article
        self.BlogPost = BlogPost

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.TextItemVersion = version_class(self.TextItem)
        self.ArticleVersion = version_class(self.Article)
        self.BlogPostVersion = version_class(self.BlogPost)

    def test_each_class_has_distinct_version_table(self):
        assert self.TextItemVersion.__table__.name == 'text_item_version'
        assert self.ArticleVersion.__table__.name == 'article_version'
        assert self.BlogPostVersion.__table__.name == 'blog_post_version'

        assert issubclass(self.ArticleVersion, self.TextItemVersion)
        assert issubclass(self.BlogPostVersion, self.TextItemVersion)

    def test_each_object_has_distinct_version_class(self):
        article = self.Article()
        blogpost = self.BlogPost()
        textitem = self.TextItem()

        self.session.add(article)
        self.session.add(blogpost)
        self.session.add(textitem)
        self.session.commit()

        # assert type(textitem.versions[0]) == self.TextItemVersion
        assert type(article.versions[0]) == self.ArticleVersion
        assert type(blogpost.versions[0]) == self.BlogPostVersion

    def test_all_tables_contain_transaction_id_column(self):
        tx_column = self.options['transaction_column_name']

        assert tx_column in self.TextItemVersion.__table__.c
        assert tx_column in self.ArticleVersion.__table__.c
        assert tx_column in self.BlogPostVersion.__table__.c

    def test_with_polymorphic(self):
        article = self.Article()
        self.session.add(article)
        self.session.commit()

        version_obj = self.session.query(self.TextItemVersion).first()
        assert isinstance(version_obj, self.ArticleVersion)

    def test_consecutive_insert_and_delete(self):
        article = self.Article()
        self.session.add(article)
        self.session.flush()
        self.session.delete(article)
        self.session.commit()

    def test_assign_transaction_id_to_both_parent_and_child_tables(self):
        tx_column = self.options['transaction_column_name']
        article = self.Article()
        self.session.add(article)
        self.session.commit()
        assert self.session.execute(
            'SELECT %s FROM article_version' % tx_column
        ).fetchone()[0]
        assert self.session.execute(
            'SELECT %s FROM text_item_version' % tx_column
        ).fetchone()[0]

    def test_primary_keys(self):
        tx_column = self.options['transaction_column_name']
        table = self.TextItemVersion.__table__
        assert len(table.primary_key.columns)
        assert 'id' in table.primary_key.columns
        assert tx_column in table.primary_key.columns
        table = self.ArticleVersion.__table__
        assert len(table.primary_key.columns)
        assert 'id' in table.primary_key.columns
        assert tx_column in table.primary_key.columns

    @pytest.mark.skipif('uses_native_versioning()')
    def test_updates_end_transaction_id_to_all_tables(self):
        if self.options['strategy'] == 'subquery':
            pytest.skip()

        end_tx_column = self.options['end_transaction_column_name']
        tx_column = self.options['transaction_column_name']
        article = self.Article()
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated article'
        self.session.commit()
        assert article.versions.count() == 2

        assert self.session.execute(
            'SELECT %s FROM text_item_version '
            'ORDER BY %s LIMIT 1' % (end_tx_column, tx_column)
        ).scalar()
        assert self.session.execute(
            'SELECT %s FROM article_version '
            'ORDER BY %s LIMIT 1' % (end_tx_column, tx_column)
        ).scalar()


create_test_cases(JoinTableInheritanceTestCase)


class TestDeepJoinedTableInheritance(TestCase):
    def create_models(self):
        class Node(self.Model):
            __versioned__ = {}
            __tablename__ = 'node'
            __mapper_args__ = dict(
                polymorphic_on='type',
                polymorphic_identity='node',
                with_polymorphic='*',
            )

            id = sa.Column(sa.Integer, primary_key=True)
            type = sa.Column(sa.String(30), nullable=False)

        class Content(Node):
            __versioned__ = {}
            __tablename__ = 'content'
            __mapper_args__ = {
                'polymorphic_identity': 'content'
            }
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey('node.id'),
                primary_key=True
            )
            description = sa.Column(sa.UnicodeText())

        class Document(Content):
            __versioned__ = {}
            __tablename__ = 'document'
            __mapper_args__ = {
                'polymorphic_identity': 'document'
            }
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey('content.id'),
                primary_key=True
            )
            body = sa.Column(sa.UnicodeText)

        self.Node = Node
        self.Content = Content
        self.Document = Document

    def test_insert(self):
        document = self.Document()
        self.session.add(document)
        self.session.commit()
        assert self.session.execute(
            'SELECT COUNT(1) FROM document_version'
        ).scalar() == 1
        assert self.session.execute(
            'SELECT COUNT(1) FROM content_version'
        ).scalar() == 1
        assert self.session.execute(
            'SELECT COUNT(1) FROM node_version'
        ).scalar() == 1
