from sqlalchemy_continuum.drivers.postgresql import PostgreSQLAdapter
from tests import TestCase


class TestPostgreSQLAdapter(TestCase):
    def test_build_triggers_sql(self):
        adapter = PostgreSQLAdapter()
        sql = adapter.build_triggers_sql([self.Article])
        assert len(sql) == 3
