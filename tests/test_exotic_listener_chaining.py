import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager
from tests import TestCase


class TestBeforeFlushListener(TestCase):
    def setup_method(self, method):
        @sa.event.listens_for(sa.orm.Session, 'before_flush')
        def before_flush(session, ctx, instances):
            for obj in session.dirty:
                obj.name = u'Updated article'

        self.before_flush = before_flush

        TestCase.setup_method(self, method)
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.session.add(self.article)
        self.session.commit()

    def teardown_method(self, method):
        TestCase.teardown_method(self, method)
        sa.event.remove(sa.orm.Session, 'before_flush', self.before_flush)

    def test_manual_tx_creation_with_no_actual_changes(self):
        self.article.name = u'Some article'

        uow = versioning_manager.unit_of_work(self.session)
        uow.create_transaction(self.session)
        self.session.flush()
