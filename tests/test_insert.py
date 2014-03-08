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
