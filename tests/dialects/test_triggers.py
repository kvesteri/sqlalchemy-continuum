import pytest

from sqlalchemy_continuum.dialects.postgresql import drop_trigger, sync_trigger
from tests import (
    QueryPool,
    TestCase,
    uses_native_versioning,
)


@pytest.mark.skipif('not uses_native_versioning()')
class TestTriggerSyncing(TestCase):
    def setup_method(self, method):
        TestCase.setup_method(self, method)

    def test_sync_triggers(self):
        sync_trigger(self.session, 'article_version')
        assert (
            'DROP TRIGGER IF EXISTS article_trigger ON "article"'
            in QueryPool.queries[-4]
        )
        assert 'DROP FUNCTION IF EXISTS article_audit' in QueryPool.queries[-3]
        assert 'CREATE OR REPLACE FUNCTION article_audit' in QueryPool.queries[-2]
        assert 'CREATE TRIGGER article_trigger' in QueryPool.queries[-1]
        sync_trigger(self.session, 'article_version')
        self.session.commit()

    def test_drop_triggers(self):
        drop_trigger(self.session, 'article')
        assert (
            'DROP TRIGGER IF EXISTS article_trigger ON "article"'
            in QueryPool.queries[-2]
        )
        assert 'DROP FUNCTION IF EXISTS article_audit' in QueryPool.queries[-1]
        self.session.commit()
