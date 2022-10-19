import pytest
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from tests import TestCase
from threading import Thread


NUM_ROWS = 100
NUM_THREADS = 4


class TestValidityStrategyMultithreaded(TestCase):
    class WrappedThread(Thread):
        """
        Wrapper around `threading.Thread` that propagates exceptions.

        REF: https://gist.github.com/sbrugman/59b3535ebcd5aa0e2598293cfa58b6ab
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.exc = None

        def run(self):
            try:
                super().run()
            except BaseException as e:
                self.exc = e

        def join(self, timeout=None):
            super().join(timeout)
            if self.exc:
                raise self.exc

    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, ),
                'strategy': 'validity'
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

        self.Article = Article

    @pytest.mark.skipif("os.environ.get('DB') == 'sqlite'")
    def test_for_deadlock_with_many_multithreaded_inserts(self):
        threads = [
            self.WrappedThread(target=self._insert_articles, args=(n,))
            for n in range(0, NUM_THREADS)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()


    def _insert_articles(self, num):
        Session = sessionmaker(bind=self.engine.connect())
        session = Session(autoflush=False)
        for i in range(1, NUM_ROWS+1):
            article = self.Article(name=f'Article {num}-{i:04}')
            session.add(article)
            session.commit()
            article.name = article.name + '.2'
            session.commit()
        assert session.query(func.count(self.Article.id)). \
               where(self.Article.name.like(f'Article {num}-%')). \
               scalar() == NUM_ROWS
