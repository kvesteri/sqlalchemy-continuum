import pytest
from sqlalchemy_continuum import versioning_manager

from tests import TestCase, uses_native_versioning


@pytest.mark.skipif('not uses_native_versioning()')
class TestRawSQL(TestCase):
    def assert_has_single_transaction(self):
        assert (
            self.session.query(versioning_manager.transaction_cls)
            .count() == 1
        )

    def test_flush_after_raw_insert(self):
        self.session.execute(
            "INSERT INTO article (name) VALUES ('some article')"
        )
        self.session.add(self.Article(name=u'some other article'))
        self.session.commit()
        self.assert_has_single_transaction()

    def test_raw_insert_after_flush(self):
        self.session.add(self.Article(name=u'some other article'))
        self.session.flush()
        self.session.execute(
            "INSERT INTO article (name) VALUES ('some article')"
        )
        self.session.commit()
        self.assert_has_single_transaction()
