import pytest
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from tests import TestCase
from threading import Thread, current_thread
from logging import getLogger, Formatter


NUM_ROWS = 100
NUM_THREADS = 4


class ThreadFormatter(Formatter):
    thread_formatter = Formatter('%(threadName)s ')

    def __init__(self, inner):
        self.inner = inner

    def format(self, record):
        return self.thread_formatter.format(record) + self.inner.format(record)


class TestValidityStrategyMultithreaded(TestCase):
    class WrappedThread(Thread):
        """
        Wrapper around `threading.Thread` that propagates exceptions
        and includes threadName in SQLAlchemy log lines.

        REF: https://gist.github.com/sbrugman/59b3535ebcd5aa0e2598293cfa58b6ab
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.exc = None

        def run(self):
            logger = getLogger('sqlalchemy.engine.Engine')

            formatters = {}
            handlers = []
            for handler in logger.handlers:
                if isinstance(handler.formatter, ThreadFormatter):
                    continue
                formatters.setdefault(handler.formatter, ThreadFormatter(handler.formatter))
                handler.setFormatter(formatters[handler.formatter])
                handlers.append(handler)

            try:
                super().run()
            except BaseException as e:
                self.exc = e

            for handler in handlers:
                handler.setFormatter(handler.formatter.inner)

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
    def test_single_objects(self):
        threads = [
            self.WrappedThread(target=self._insert_update_single_article)
            for n in range(0, NUM_THREADS)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()


    def _insert_update_single_article(self):
        Session = sessionmaker(bind=self.engine.connect())
        session = Session(autoflush=False)
        name = current_thread().name
        for i in range(1, NUM_ROWS+1):
            article = self.Article(name=f'Article {name}-{i:04}')
            session.add(article)
            session.commit()
            article.name += '.2'
            session.commit()
        assert session.query(func.count(self.Article.id)). \
               where(self.Article.name.like(f'Article {name}-%')). \
               scalar() == NUM_ROWS


    @pytest.mark.skipif("os.environ.get('DB') == 'sqlite'")
    def test_multiple_objects(self):
        threads = [
            self.WrappedThread(target=self._insert_update_multiple_articles)
            for n in range(0, NUM_THREADS)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()


    def _insert_update_multiple_articles(self):
        Session = sessionmaker(bind=self.engine.connect())
        session = Session(autoflush=False)
        name = current_thread().name
        for i in range(1, NUM_ROWS+1):
            article1 = self.Article(name=f'Article 1 {name}-{i:04}')
            article2 = self.Article(name=f'Article 2 {name}-{i:04}')
            session.add_all([article1, article2])
            session.commit()
            article1.name += '.2'
            article2.name += '.2'
            session.commit()
        assert session.query(func.count(self.Article.id)). \
               where(self.Article.name.like(f'Article 1 {name}-%')). \
               scalar() == NUM_ROWS
        assert session.query(func.count(self.Article.id)). \
               where(self.Article.name.like(f'Article 2 {name}-%')). \
               scalar() == NUM_ROWS

