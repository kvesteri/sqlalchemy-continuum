from pytest import raises
from sqlalchemy.orm.session import Session
from sqlalchemy_continuum import versioning_manager, UnitOfWork
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

    def test_manual_transaction_creation(self):
        uow = versioning_manager.unit_of_work(self.session)
        transaction = uow.create_transaction(self.session)
        self.session.flush()
        assert transaction.id == 1
        article = self.Article(name=u'Session1 article')
        self.session.add(article)
        self.session.flush()
        assert uow.current_transaction.id == 1

        self.session.commit()
        assert article.versions[-1].transaction_id == 1

    def test_commit_without_objects(self):
        self.session.commit()


class TestUnitOfWork(TestCase):
    def test_with_session_arg(self):
        uow = versioning_manager.unit_of_work(self.session)
        assert isinstance(uow, UnitOfWork)

    def test_with_connection_arg(self):
        uow = versioning_manager.unit_of_work(self.session.bind)
        assert isinstance(uow, UnitOfWork)

    def test_with_entity_arg(self):
        article = self.Article()
        self.session.add(article)
        uow = versioning_manager.unit_of_work(article)
        assert isinstance(uow, UnitOfWork)

    def test_raises_type_error_for_unknown_type(self):
        with raises(TypeError):
            versioning_manager.unit_of_work(None)
