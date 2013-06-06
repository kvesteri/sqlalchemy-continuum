import sqlalchemy as sa
from sqlalchemy_continuum import Versioned
from tests import TestCase


class TestTableBuilder(TestCase):
    def test_assigns_foreign_keys_for_versions(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        cls = self.Tag.__versioned__['class']
        version = self.session.query(cls).first()
        assert version.name == u'some tag'
        assert version.id == 1
        assert version.article_id == 1

    def test_versioned_table_structure(self):
        table = self.Article.__versioned__['class'].__table__
        assert 'id' in table.c
        assert 'name' in table.c
        assert 'content' in table.c
        assert 'description'in table.c


class TestTableBuilderWithColumnOrderInspection(TestCase):
    def create_models(self):
        # We create the table this way since SQLAlchemy does not allow having
        # two table objects with same name in the same metadata.
        self.engine.execute(
            """
            CREATE TABLE article (
                id SERIAL,
                name VARCHAR(255),
                content VARCHAR(255),
                description VARCHAR(255),
                PRIMARY KEY(id)
            )
            """
        )

        class Article(self.Model, Versioned):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, ),
                'inspect_column_order': True
            }
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)
            name = sa.Column(sa.Unicode(255))
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.Article = Article
        self.Article.metadata.bind = self.connection

    def create_tables(self):
        pass

    def drop_tables(self):
        self.engine.execute('DROP TABLE article')

    def test_table_column_order_is_reflected_from_parent(self):
        # Sometimes user may switch the order of columns in model class. We
        # need to test that versioned table builder is able to inspect the
        # column order. Column order only needs to inspected when creating the
        # table.
        ordered_column_names = [
            'id', 'name', 'content', 'description', 'transaction_id'
        ]

        self.Article.metadata.bind = self.connection
        article_history = self.Article.metadata.tables['article_history']
        assert ordered_column_names == article_history.c.keys()


class TestUpdate(TestCase):
    def test_creates_versions_on_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'

        self.session.commit()
        self.session.refresh(article)
        version = article.versions.all()[-1]
        assert version.name == u'Updated name'
        assert version.content == u'Updated content'
        assert version.transaction.id == version.transaction_id
