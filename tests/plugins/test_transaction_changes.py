from sqlalchemy_continuum import history_class
from sqlalchemy_continuum.plugins import TransactionChangesPlugin
from tests import TestCase


class TestTransactionChagnes(TestCase):
    plugins = [TransactionChangesPlugin()]

    def test_has_relation_to_changes(self):
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.article.tags.append(self.Tag(name=u'Some tag'))
        self.session.add(self.article)
        self.session.commit()
        tx = self.article.versions[0].transaction
        assert tx.changes


class TestTransactionLogChangedEntities(TestCase):
    plugins = [TransactionChangesPlugin()]

    def test_change_single_entity(self):
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.session.add(self.article)
        self.session.commit()
        tx = self.article.versions[0].transaction

        assert tx.changed_entities == {
            history_class(self.article.__class__):
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
