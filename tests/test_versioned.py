import sqlalchemy as sa
from tests import TestCase


class TestVersionModelBuilding(TestCase):
    def test_builds_relationship(self):
        assert self.Article.versions

    def test_parent_has_versioned_class_defined(self):
        assert self.Article.__versioned__['class']

    def test_versioned_model_has_table_object(self):
        assert isinstance(
            self.Article.__versioned__['class'].__table__, sa.Table
        )

    def test_multiple_consecutive_flushes(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.flush()
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.flush()
        self.session.commit()

    def test_relationships(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        version = article.versions.all()[0]
        assert version.name == u'Some article'
        assert version.content == u'Some content'
        version = article.tags[0].versions.all()[0]
        assert version.name == u'some tag'
