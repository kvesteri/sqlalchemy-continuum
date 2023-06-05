import pytest

from tests import TestCase


class TestSavepoints(TestCase):
    def test_flush_and_nested_rollback(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.flush()
        savepoint = self.session.begin_nested()
        self.session.add(self.Article(name=u'Some article'))
        article.name = u'Updated name'
        savepoint.rollback()
        self.session.commit()
        assert article.versions.count() == 1
        assert list(article.versions)[-1].name == u'Some article'

    def test_partial_rollback(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        savepoint = self.session.begin_nested()
        self.session.add(self.Article(name=u'Some article'))
        article.name = u'Updated name'
        savepoint.rollback()
        self.session.commit()
        assert article.versions.count() == 1
        assert list(article.versions)[-1].name == u'Some article'

    def test_multiple_savepoints(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.flush()
        savepoint = self.session.begin_nested()
        article.name = u'Updated name'
        savepoint.commit()
        savepoint2 = self.session.begin_nested()
        article.name = u'Another article'
        self.session.commit()
        assert article.versions.count() == 1
        assert list(article.versions)[-1].name == u'Another article'
