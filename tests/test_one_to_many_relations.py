from tests import TestCase


class TestVersionedModel(TestCase):
    def test_versioned_model_copies_relationships(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tags

    def test_relationship_primaryjoin(self):
        ArticleHistory = self.Article.__versioned__['class']
        assert str(ArticleHistory.tags.property.primaryjoin) == (
            "article_history.id = tag_history.article_id "
            "AND tag_history.transaction_id = "
            "(SELECT max(tag_history.transaction_id) AS max_1 \n"
            "FROM tag_history, article_history \n"
            "WHERE tag_history.transaction_id <= "
            "article_history.transaction_id)"
        )
