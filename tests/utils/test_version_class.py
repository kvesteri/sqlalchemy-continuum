from pytest import raises
from sqlalchemy_continuum import ClassNotVersioned, version_class
from sqlalchemy_continuum.manager import VersioningManager
from sqlalchemy_continuum.model_builder import ModelBuilder

from tests import TestCase


class TestVersionClass(TestCase):
    def test_version_class_for_versioned_class(self):
        ArticleVersion = version_class(self.Article)
        assert ArticleVersion.__name__ == 'ArticleVersion'

    def test_throws_error_for_non_versioned_class(self):
        with raises(ClassNotVersioned):
            version_class('invalid')

    def test_module_name_in_class_name(self):
        options = {'use_module_name': True}
        vm = VersioningManager(options=options)
        mb = ModelBuilder(vm, self.Article)
        ArticleVersion = mb.build_model(self.Article.__table__)
        assert ArticleVersion.__name__ == 'TestsArticleVersion'
