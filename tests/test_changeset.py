from tests import TestCase


class TestChangeSet(TestCase):
    def test_changeset_for_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].changeset == {
            'content': [None, u'Some content'],
            'name': [None, u'Some article'],
            'id': [None, 1]
        }

    def test_changeset_for_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()

        assert article.versions[1].changeset == {
            'content': [u'Some content', u'Updated content'],
            'name': [u'Some article', u'Updated name']
        }
