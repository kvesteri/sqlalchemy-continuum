from sqlalchemy_continuum import changeset
from tests import TestCase


class TestChangeSet(TestCase):
    def test_changeset_for_new_value(self):
        article = self.Article(name=u'Some article')
        assert changeset(article) == {'name': [u'Some article', None]}

    def test_changeset_for_deletion(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.commit()
        self.session.delete(article)
        assert changeset(article) == {'name': [None, u'Some article']}

    def test_changeset_for_update(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.commit()
        article.tags
        article.name = u'Updated article'
        assert changeset(article) == {
            'name': [u'Updated article', u'Some article']
        }
