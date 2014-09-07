import pytest
from tests import TestCase, uses_native_versioning


@pytest.mark.skipif('not uses_native_versioning()')
class TestRawSQL(TestCase):
    def test_single_statement(self):
        self.session.execute(
            "INSERT INTO article (name) VALUES ('some article')"
        )
        assert self.session.execute(
            "SELECT COUNT(1) FROM transaction"
        ).scalar() == 1

    def test_multiple_statements(self):
        self.session.execute(
            "INSERT INTO article (name) VALUES ('some article')"
        )
        self.session.execute(
            "INSERT INTO article (name) VALUES ('some article')"
        )
        assert self.session.execute(
            "SELECT COUNT(1) FROM transaction"
        ).scalar() == 1
