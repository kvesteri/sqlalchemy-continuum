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
