from tests import TestCase


class TestVersionModelBuilder(TestCase):
    def test_builds_relationship(self):
        assert self.Article.versions

    def test_parent_has_access_to_versioning_manager(self):
        assert self.Article.__versioning_manager__


    def test_column_properties(self):
        article = self.Article()
        article.name = u'Name'
        article.content = u'Content'
        article.description = u'Desc'
        self.session.add(article)
        self.session.commit()

        article_version = article.versions[0]
        assert article.fulltext_content == article.name + article.content + article.description
        assert article.fulltext_content == article_version.fulltext_content
