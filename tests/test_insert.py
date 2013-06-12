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
