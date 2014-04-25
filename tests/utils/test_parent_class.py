from pytest import raises
from sqlalchemy_continuum import parent_class, version_class

from tests import TestCase


class TestParentClass(TestCase):
    def test_parent_class_for_version_class(self):
        ArticleVersion = version_class(self.Article)
        assert parent_class(ArticleVersion) == self.Article

    def test_throws_error_for_non_version_class(self):
        with raises(KeyError):
            parent_class(self.Article)
