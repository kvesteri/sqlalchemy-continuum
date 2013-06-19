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

    def test_changed_entities(self):
        tx = self.article.versions[0].transaction

        assert self.article.versions[0] in tx.changed_entities[
            self.ArticleHistory
        ]
        assert self.article.tags[0].versions[0] in tx.changed_entities[
            self.TagHistory
        ]

    def test_has_relation_to_changes(self):
        tx = self.article.versions[0].transaction
        assert tx.changes

    def test_has_meta_parameter(self):
        tx = self.article.versions[0].transaction
        assert tx.meta is None

        tx.meta = {'some key': 'some value'}
        self.session.commit()
        self.session.refresh(tx)
        assert tx.meta == {'some key': 'some value'}

    def test_tx_meta_context_manager(self):
        self.article.name = u'Some update article'
        with versioning_manager.tx_meta(some_key=u'some_value'):
            self.session.commit()
        self.article.versions[-1].transaction.meta['some_key'] == u'some_value'
