from sqlalchemy_continuum import versioning_manager
from sqlalchemy_continuum.plugins import TransactionMetaPlugin
from tests import TestCase


class TestTransaction(TestCase):
    plugins = [TransactionMetaPlugin()]

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.article.tags.append(self.Tag(name=u'Some tag'))
        self.session.add(self.article)
        self.session.commit()

    def test_has_meta_attribute(self):
        tx = self.article.versions[0].transaction
        assert tx.meta == {}

        tx.meta = {u'some key': u'some value'}
        self.session.commit()
        self.session.refresh(tx)
        assert tx.meta == {u'some key': u'some value'}

    def test_tx_meta_manager(self):
        self.article.name = u'Some update article'
        meta = {u'some_key': u'some_value'}
        with versioning_manager.unit_of_work(self.session).tx_meta(**meta):
            self.session.commit()

        tx = self.article.versions[-1].transaction
        assert tx.meta[u'some_key'] == u'some_value'

    def test_passing_callables_for_tx_meta(self):
        self.article.name = u'Some update article'
        meta = {u'some_key': lambda: self.article.id}
        with versioning_manager.unit_of_work(self.session).tx_meta(**meta):
            self.session.commit()
        tx = self.article.versions[-1].transaction
        assert tx.meta[u'some_key'] == str(self.article.id)

    def test_only_saves_meta_if_actual_moficication(self):
        self.article.name = u'Some article'
        self.session.commit()
        meta = {u'some_key': u'some_value'}
        with versioning_manager.unit_of_work(self.session).tx_meta(**meta):
            self.article.name = u'Some article'
            self.session.commit()
        assert self.session.query(
            versioning_manager.transaction_meta_cls
        ).count() == 0
