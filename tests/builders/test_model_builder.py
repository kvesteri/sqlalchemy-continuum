from tests import TestCase


class TestVersionModelBuilder(TestCase):
    def test_builds_relationship(self):
        assert self.Article.versions

    def test_parent_has_access_to_versioning_manager(self):
        assert self.Article.__versioning_manager__
