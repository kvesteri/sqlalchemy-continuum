import sqlalchemy as sa
from sqlalchemy_continuum import count_versions, versioning_manager

from tests import TestCase


class TestInsert(TestCase):
    def _insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        return article

    def test_insert_creates_version(self):
        article = self._insert()
        version = article.versions.all()[-1]
        assert version.name == u'Some article'
        assert version.content == u'Some content'
        assert version.transaction.id == version.transaction_id

    def test_stores_operation_type(self):
        article = self._insert()
        assert article.versions[0].operation_type == 0

    def test_multiple_consecutive_flushes(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.flush()
        article2 = self.Article()
        article2.name = u'Some article'
        article2.content = u'Some content'
        self.session.add(article2)
        self.session.flush()
        self.session.commit()
        assert article.versions.count() == 1
        assert article2.versions.count() == 1


class TestInsertWithDeferredColumn(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.orm.deferred(sa.Column(sa.Unicode(255)))

        self.TextItem = TextItem

    def test_insert(self):
        item = self.TextItem()
        self.session.add(item)
        self.session.commit()
        assert count_versions(item) == 1


class TestInsertNonVersionedObject(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.orm.deferred(sa.Column(sa.Unicode(255)))

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.orm.deferred(sa.Column(sa.Unicode(255)))

        self.TextItem = TextItem

    def test_does_not_create_transaction(self):
        item = self.TextItem()
        self.session.add(item)
        self.session.commit()

        assert self.session.query(
            versioning_manager.transaction_cls
        ).count() == 0
