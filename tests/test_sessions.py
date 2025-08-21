from sqlalchemy.orm.session import Session

from sqlalchemy_continuum import UnitOfWork, versioning_manager
from tests import TestCase


class TestSessions(TestCase):
    plugins = []

    def test_new_session(self):
        self.session2 = Session(bind=self.engine)
        article = self.Article(name='Session2 article')
        self.session2.add(article)
        self.session2.commit()
        assert list(article.versions)[-1].transaction_id

    def test_multiple_connections(self):
        self.session2 = Session(bind=self.engine.connect())
        article = self.Article(name='Session1 article')
        article2 = self.Article(name='Session2 article')
        self.session.add(article)
        self.session2.add(article2)
        self.session.flush()
        self.session2.flush()

        self.session.commit()
        self.session2.commit()
        assert list(article.versions)[-1].transaction_id
        assert (
            list(article2.versions)[-1].transaction_id
            > list(article.versions)[-1].transaction_id
        )

    def test_manual_transaction_creation(self):
        uow = versioning_manager.unit_of_work(self.session)
        transaction = uow.create_transaction(self.session)
        self.session.flush()
        assert transaction.id
        article = self.Article(name='Session1 article')
        self.session.add(article)
        self.session.flush()
        assert uow.current_transaction.id

        self.session.commit()
        assert list(article.versions)[-1].transaction_id

    def test_commit_without_objects(self):
        self.session.commit()


class TestUnitOfWork(TestCase):
    def test_with_session_arg(self):
        uow = versioning_manager.unit_of_work(self.session)
        assert isinstance(uow, UnitOfWork)


class TestExternalTransactionSession(TestCase):
    def test_session_with_external_transaction(self):
        conn = self.engine.connect()
        t = conn.begin()
        session = Session(bind=conn)

        article = self.Article(name='My Session Article')
        session.add(article)
        session.flush()

        session.close()
        t.rollback()
        conn.close()
