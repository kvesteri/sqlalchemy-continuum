import sqlalchemy as sa
from sqlalchemy_continuum import Operation, version_class

from tests import TestCase


class TestDelete(TestCase):
    def _delete(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        self.session.delete(article)
        self.session.commit()

    def test_stores_operation_type(self):
        self._delete()
        versions = self.session.query(self.ArticleVersion).all()
        assert versions[1].operation_type == 2

    def test_creates_versions_on_delete(self):
        self._delete()
        versions = self.session.query(self.ArticleVersion).all()
        assert len(versions) == 2
        assert versions[1].name == u'Some article'
        assert versions[1].content == u'Some content'

    def test_insert_delete_in_single_transaction(self):
        """Test that when an object is created and then deleted within the
        same transaction, no history entry is created.
        """
        article = self.Article(name=u'Article name')
        self.session.add(article)
        self.session.flush()

        self.session.delete(article)
        self.session.commit()

        ArticleVersion = version_class(self.Article)
        assert self.session.query(ArticleVersion).count() == 0

    def test_update_delete_in_single_transaction(self):
        """Test that when an object is updated and then deleted within the
        same transaction, the operation type DELETE is stored.
        """
        article = self.Article(name=u'Article name')
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        self.session.flush()
        self.session.delete(article)
        self.session.commit()

        ArticleVersion = version_class(self.Article)
        versions_query = self.session.query(self.ArticleVersion)
        assert versions_query.count() == 2
        assert versions_query[1].operation_type == Operation.DELETE

    def test_modify_primary_key(self):
        """Test that modifying the primary key within the same transaction
        maintains correct delete behavior"""
        article = self.Article(name=u'Article name')
        self.session.add(article)
        self.session.commit()

        article.name = u'Second name'
        self.session.flush()
        article.id += 1
        self.session.delete(article)
        self.session.commit()

        ArticleVersion = version_class(self.Article)
        versions_q = self.session.query(ArticleVersion)\
                        .order_by(ArticleVersion.transaction_id)
        assert versions_q.count() == 2
        assert versions_q[1].operation_type == Operation.DELETE


class TestDeleteWithDeferredColumn(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.orm.deferred(sa.Column(sa.Unicode(255)))

        self.TextItem = TextItem

    def test_insert_and_delete(self):
        item = self.TextItem()
        self.session.add(item)
        self.session.commit()
        self.session.delete(item)
        self.session.commit()
