from datetime import datetime
import sqlalchemy as sa

from tests import TestCase
from sqlalchemy_continuum import versioning_manager


class TestTransactionLog(TestCase):
    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.article.tags.append(self.Tag(name=u'Some tag'))
        self.session.add(self.article)
        self.session.commit()

    def test_relationships(self):
        tx = self.article.versions[0].transaction
        assert tx.id == self.article.versions[0].transaction_id
        assert tx.articles == [self.article.versions[0]]

    def test_has_relation_to_changes(self):
        tx = self.article.versions[0].transaction
        assert tx.changes

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
        with versioning_manager.tx_meta(**meta):
            self.session.commit()

        tx = self.article.versions[-1].transaction
        assert tx.meta[u'some_key'] == u'some_value'

    def test_passing_callables_for_tx_meta(self):
        self.article.name = u'Some update article'
        meta = {u'some_key': lambda: self.article.id}
        with versioning_manager.tx_meta(**meta):
            self.session.commit()
        tx = self.article.versions[-1].transaction
        assert tx.meta[u'some_key'] == str(self.article.id)

    def test_only_saves_transaction_if_actual_modifications(self):
        self.article.name = u'Some article'
        self.session.commit()
        self.article.name = u'Some article'
        self.session.commit()
        assert self.session.query(
            versioning_manager.transaction_log_cls
        ).count() == 1

    def test_only_saves_meta_if_actual_moficication(self):
        self.article.name = u'Some article'
        self.session.commit()
        meta = {u'some_key': u'some_value'}
        with versioning_manager.tx_meta(**meta):
            self.article.name = u'Some article'
            self.session.commit()
        assert self.session.query(
            versioning_manager.transaction_meta_cls
        ).count() == 0


class TestTransactionLogChangedEntities(TestCase):
    def test_change_single_entity(self):
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.session.add(self.article)
        self.session.commit()
        tx = self.article.versions[0].transaction

        assert tx.changed_entities == {
            self.article.__versioned__['class']:
            [self.article.versions[0]]
        }

    def test_change_multiple_entities(self):
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.article.tags.append(self.Tag(name=u'Some tag'))
        self.session.add(self.article)
        self.session.commit()
        tx = self.article.versions[0].transaction

        assert self.article.versions[0] in tx.changed_entities[
            self.ArticleHistory
        ]
        assert self.article.tags[0].versions[0] in tx.changed_entities[
            self.TagHistory
        ]
