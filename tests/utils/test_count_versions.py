from sqlalchemy_continuum import count_versions
from tests import TestCase


class TestCountVersions(TestCase):
    def test_count_versions_without_versions(self):
        article = self.Article(name=u'Some article')
        assert count_versions(article) == 0

    def test_count_versions_with_initial_version(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.commit()
        assert count_versions(article) == 1

    def test_count_versions_with_multiple_versions(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated article'
        self.session.commit()
        assert count_versions(article) == 2

    def test_count_versions_with_multiple_objects(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        article2 = self.Article(name=u'Some article')
        self.session.add(article2)
        self.session.commit()
        assert count_versions(article) == 1
