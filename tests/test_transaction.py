import pytest
from sqlalchemy_continuum import versioning_manager
from tests import TestCase, uses_native_versioning


class TestTransaction(TestCase):
    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.article = self.Article()
        self.article.name = u'Some article'
        self.article.content = u'Some content'
        self.article.tags.append(self.Tag(name=u'Some tag'))
        self.session.add(self.article)
        self.session.commit()

    def test_relationships(self):
        assert self.article.versions[0].transaction

    def test_only_saves_transaction_if_actual_modifications(self):
        self.article.name = u'Some article'
        self.session.commit()
        self.article.name = u'Some article'
        self.session.commit()
        assert self.session.query(
            versioning_manager.transaction_cls
        ).count() == 1

    def test_repr(self):
        transaction = self.session.query(
            versioning_manager.transaction_cls
        ).first()
        assert (
            '<Transaction id=%r, issued_at=%r>' % (
                transaction.id,
                transaction.issued_at
            ) ==
            repr(transaction)
        )


@pytest.mark.skipif('not uses_native_versioning()')
class TestNativeVersioning(TestCase):
    def test_transaction_id_collision(self):
        tx_id = self.session.execute('SELECT txid_current()').scalar()
        self.session.execute(
            'INSERT INTO transaction (id) VALUES (%d)' % (tx_id + 1)
        )
        self.session.commit()
        self.article = self.Article(name=u'Some article')
        self.session.add(self.article)
        self.session.commit()
