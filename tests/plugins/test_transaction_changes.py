from six import PY3
from tests import TestCase


class TestTransactionChagnes(TestCase):
    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.article.tags.append(self.Tag(name=u'Some tag'))
        self.session.add(self.article)
        self.session.commit()

    def test_has_relation_to_changes(self):
        tx = self.article.versions[0].transaction
        assert tx.changes


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
