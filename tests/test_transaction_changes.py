from tests import TestCase


class TestTransactionChanges(TestCase):
    def test_saves_changed_entity_names(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        tx = article.versions[0].transaction
        assert tx.changes[0].entity_name == u'Article'
        assert article.versions[0].changes[0] == tx.changes[0]
