from tests import TestCase


class TestTransactionLog(TestCase):
    def test_relationships(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        tx = article.versions[0].transaction
        assert tx.id == article.versions[0].transaction_id
        assert tx.articles == [article.versions[0]]

    def test_all_affected_entities(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()

        tx = article.versions[0].transaction

        assert article.versions[0] in tx.all_affected_entities[
            self.ArticleHistory
        ]
        assert article.tags[0].versions[0] in tx.all_affected_entities[
            self.TagHistory
        ]
