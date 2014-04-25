from pytest import raises
from sqlalchemy_continuum import ClassNotVersioned, version_class

from tests import TestCase


class TestVersionClass(TestCase):
    def test_version_class_for_versioned_class(self):
        ArticleVersion = version_class(self.Article)
        assert ArticleVersion.__name__ == 'ArticleVersion'

    def test_throws_error_for_non_versioned_class(self):
        with raises(ClassNotVersioned):
            version_class('invalid')
