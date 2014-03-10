from sqlalchemy.orm.session import Session
from tests import TestCase


class TestSessions(TestCase):
    plugins = []

    def test_multiple_connections(self):
        self.session2 = Session(bind=self.engine.connect())
        article = self.Article(name=u'Session1 article')
        article2 = self.Article(name=u'Session2 article')
        self.session.add(article)
        self.session2.add(article2)
        self.session.flush()
        self.session2.flush()

        self.session.commit()
        self.session2.commit()
        assert article.versions[-1].transaction_id == 1
        assert article2.versions[-1].transaction_id == 2
