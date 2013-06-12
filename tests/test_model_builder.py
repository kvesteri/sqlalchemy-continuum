import sqlalchemy as sa
from tests import TestCase


class TestVersionModelBuilder(TestCase):
    def test_builds_relationship(self):
        assert self.Article.versions

    def test_parent_has_versioned_class_defined(self):
        assert self.Article.__versioned__['class']

    def test_versioned_model_has_table_object(self):
        assert isinstance(
            self.Article.__versioned__['class'].__table__, sa.Table
        )

    def test_parent_has_access_to_versioning_manager(self):
        assert self.Article.__versioned__['manager']

    def test_parent_has_access_to_transaction_log(self):
        assert self.Article.__versioned__['transaction_log']
