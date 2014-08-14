import pytest
from sqlalchemy_continuum.plugins import NullDeletePlugin
from tests import TestCase, uses_native_versioning


class DeleteTestCase(TestCase):
    def _delete(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        self.session.delete(article)
        self.session.commit()

    def test_stores_operation_type(self):
        self._delete()
        versions = self.session.query(self.ArticleVersion).all()
        assert versions[1].operation_type == 2


@pytest.mark.skipif('uses_native_versioning()')
class TestDeleteWithoutStoreDataAtDelete(DeleteTestCase):
    plugins = [NullDeletePlugin()]

    def test_creates_versions_on_delete(self):
        self._delete()
        versions = self.session.query(self.ArticleVersion).all()
        assert len(versions) == 2
        assert versions[1].name is None
        assert versions[1].content is None
