from sqlalchemy_continuum import changeset
from tests import TestCase


class TestChangeSet(TestCase):
    def test_changeset_for_new_value(self):
        article = self.Article(name='Some article')
        assert changeset(article) == {'name': ['Some article', None]}

    def test_changeset_for_deletion(self):
        article = self.Article(name='Some article')
        self.session.add(article)
        self.session.commit()
        self.session.delete(article)
        assert changeset(article) == {'name': [None, 'Some article']}

    def test_changeset_for_update(self):
        article = self.Article(name='Some article')
        self.session.add(article)
        self.session.commit()
        article.tags
        article.name = 'Updated article'
        assert changeset(article) == {'name': ['Updated article', 'Some article']}
