from sqlalchemy_continuum import versioning_manager
from tests import TestCase


class TestTransaction(TestCase):
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

    def test_only_saves_transaction_if_actual_modifications(self):
        self.article.name = u'Some article'
        self.session.commit()
        self.article.name = u'Some article'
        self.session.commit()
        assert self.session.query(
            versioning_manager.transaction_cls
        ).count() == 1
