import sqlalchemy as sa
import sqlmodel
from sqlalchemy_continuum import versioning_manager

from tests.sqlmodel import SQLModelTestCase


class TestInsertSQLModel(SQLModelTestCase):
    def _insert(self):
        article = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article)
        self.session.commit()
        return article

    def test_insert_creates_version(self):
        article = self._insert()
        version = list(article.versions)[-1]
        assert version.name == u'Some article'
        assert version.content == u'Some content'
        assert version.transaction.id == version.transaction_id

    def test_stores_operation_type(self):
        article = self._insert()
        assert article.versions[0].operation_type == 0

    def test_multiple_consecutive_flushes(self):
        article = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article)
        self.session.flush()
        article2 = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article2)
        self.session.flush()
        self.session.commit()
        assert article.versions.count() == 1
        assert article2.versions.count() == 1


class TestInsertNonVersionedObjectSQLModel(SQLModelTestCase):
    def create_models(self):
        self.Model = sqlmodel.SQLModel
        class TextItem(self.Model, table=True):
            __tablename__ = 'text_item'
            id: int | None = sqlmodel.Field(default=None, primary_key=True)
            name: str = sqlmodel.Field(sa.Unicode(255))

        class Tag(self.Model, table=True):
            __tablename__ = 'tag'
            __versioned__ = {}
            id: int | None = sqlmodel.Field(default=None, primary_key=True)
            name: str = sqlmodel.Field(sa.Unicode(255))

        self.TextItem = TextItem
        self.Tag = Tag

    def teardown_method(self, method):
        super().teardown_method(method)
        self.Model.metadata.remove(self.TextItem.__table__)
        self.Model.metadata.remove(self.Tag.__table__)

    def test_does_not_create_transaction(self):
        item = self.TextItem(name="test")
        self.session.add(item)
        self.session.commit()

        assert self.session.query(
            versioning_manager.transaction_cls
        ).count() == 0
