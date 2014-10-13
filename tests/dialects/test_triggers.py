import os

import pytest
import sqlalchemy as sa

from sqlalchemy_continuum.dialects.postgresql import (
    drop_trigger,
    sync_trigger
)
from tests import (
    get_dns_from_driver,
    get_driver_name,
    QueryPool,
    uses_native_versioning
)


@pytest.mark.skipif('not uses_native_versioning()')
class TestTriggerSyncing(object):
    def setup_method(self, method):
        driver = os.environ.get('DB', 'sqlite')
        self.driver = get_driver_name(driver)
        self.engine = sa.create_engine(get_dns_from_driver(self.driver))
        self.connection = self.engine.connect()
        if driver == 'postgres-native':
            self.connection.execute('CREATE EXTENSION IF NOT EXISTS hstore')

        self.connection.execute(
            'CREATE TABLE article '
            '(id INT PRIMARY KEY, name VARCHAR(200), content TEXT)'
        )
        self.connection.execute(
            'CREATE TABLE article_version '
            '(id INT, transaction_id INT, name VARCHAR(200), '
            'name_mod BOOLEAN, PRIMARY KEY (id, transaction_id))'
        )

    def teardown_method(self, method):
        self.connection.execute('DROP TABLE IF EXISTS article')
        self.connection.execute('DROP TABLE IF EXISTS article_version')
        self.engine.dispose()
        self.connection.close()

    def test_sync_triggers(self):
        sync_trigger(self.connection, 'article_version')
        assert (
            'DROP TRIGGER IF EXISTS article_trigger ON "article"'
            in QueryPool.queries[-4]
        )
        assert 'DROP FUNCTION ' in QueryPool.queries[-3]
        assert 'CREATE OR REPLACE FUNCTION ' in QueryPool.queries[-2]
        assert 'CREATE TRIGGER ' in QueryPool.queries[-1]
        sync_trigger(self.connection, 'article_version')

    def test_drop_triggers(self):
        drop_trigger(self.connection, 'article')
        assert (
            'DROP TRIGGER IF EXISTS article_trigger ON "article"'
            in QueryPool.queries[-2]
        )
        assert 'DROP FUNCTION ' in QueryPool.queries[-1]
