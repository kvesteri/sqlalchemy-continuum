from sqlalchemy_continuum import version_class
from sqlalchemy_continuum.plugins import TransactionChangesPlugin
from tests import TestCase


class TestTransactionChanges(TestCase):
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


class TestTransactionChangedEntities(TestCase):
    plugins = [TransactionChangesPlugin()]

    def test_change_single_entity(self):
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.session.add(self.article)
        self.session.commit()
        tx = self.article.versions[0].transaction

        assert tx.changed_entities == {
            version_class(self.article.__class__):
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
            self.ArticleVersion
        ]
        assert self.article.tags[0].versions[0] in tx.changed_entities[
            self.TagVersion
        ]

    def test_saves_changed_entity_names(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        tx = article.versions[0].transaction
        assert tx.changes[0].entity_name == u'Article'

    def test_saves_only_modified_entity_names(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        TransactionChanges = article.__versioned__['transaction_changes']

        article.name = u'Some article'
        self.session.commit()

        assert self.session.query(TransactionChanges).count() == 1
