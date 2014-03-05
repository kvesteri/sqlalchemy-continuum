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
        versions = self.session.query(self.ArticleHistory).all()
        assert versions[1].operation_type == 2

    def test_creates_versions_on_delete(self):
        self._delete()
        versions = self.session.query(self.ArticleHistory).all()
        assert len(versions) == 2
        assert versions[1].name == u'Some article'
        assert versions[1].content == u'Some content'
