import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


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
        self.TextItemVersion = version_class(self.TextItem)
        self.ArticleVersion = version_class(self.Article)
        self.BlogPostVersion = version_class(self.BlogPost)


class TestJoinTableInheritance(JoinTableInheritanceTestCase):
    versioning_strategy = 'validity'

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

        assert type(textitem.versions[0]) == self.TextItemVersion
        assert type(article.versions[0]) == self.ArticleVersion
        assert type(blogpost.versions[0]) == self.BlogPostVersion

    def test_all_tables_contain_transaction_id_column(self):
        assert 'transaction_id' in self.TextItemVersion.__table__.c
        assert 'transaction_id' in self.ArticleVersion.__table__.c
        assert 'transaction_id' in self.BlogPostVersion.__table__.c

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
        article = self.Article()
        self.session.add(article)
        self.session.commit()
        assert self.session.execute(
            'SELECT transaction_id FROM article_version'
        ).fetchone()[0] == 1
        assert self.session.execute(
            'SELECT transaction_id FROM text_item_version'
        ).fetchone()[0] == 1

    def test_primary_keys(self):
        table = self.TextItemVersion.__table__
        assert len(table.primary_key.columns)
        assert 'id' in table.primary_key.columns
        assert 'transaction_id' in table.primary_key.columns
        table = self.ArticleVersion.__table__
        assert len(table.primary_key.columns)
        assert 'id' in table.primary_key.columns
        assert 'transaction_id' in table.primary_key.columns

    def test_updates_end_transaction_id_to_all_tables(self):
        article = self.Article()
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated article'
        self.session.commit()
        assert article.versions.count() == 2
        assert self.session.execute(
            'SELECT end_transaction_id FROM text_item_version '
            'ORDER BY transaction_id LIMIT 1'
        ).scalar()
        assert self.session.execute(
            'SELECT end_transaction_id FROM article_version '
            'ORDER BY transaction_id LIMIT 1'
        ).scalar()
