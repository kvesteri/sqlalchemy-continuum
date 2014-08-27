from tests import TestCase


class TestSavepoints(TestCase):
    def test_nested_transactions(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.flush()
        self.session.begin_nested()
        self.session.add(self.Article(name=u'Some article'))
        article.name = u'Updated name'
        self.session.rollback()
        self.session.commit()
        assert (
            self.session.execute(
                'SELECT COUNT(1) FROM article_version'
            ).scalar() == 1
        )
