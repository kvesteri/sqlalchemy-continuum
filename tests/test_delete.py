from tests import TestCase


class TestDelete(TestCase):
    def test_creates_versions_on_delete(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        self.session.delete(article)
        self.session.commit()

        versions = self.session.query(self.ArticleHistory).all()
        assert len(versions) == 2
        assert versions[1].name is None
        assert versions[1].content is None
