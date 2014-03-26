from copy import copy

import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from sqlalchemy_continuum.plugins import PropertyModTrackerPlugin
from sqlalchemy_continuum.schema import update_property_mod_flags
from tests import TestCase


class TestSchemaTools(TestCase):
    versioning_strategy = 'validity'
    plugins = [PropertyModTrackerPlugin()]

    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)

        self.Article = Article

    def _insert(self, values):
        table = version_class(self.Article).__table__
        stmt = table.insert().values(values)
        self.session.execute(stmt)

    def test_something(self):
        table = version_class(self.Article).__table__
        self._insert(
            {
                'id': 1,
                'transaction_id': 1,
                'end_transaction_id': 2,
                'name': u'Article 1',
                'name_mod': False,
                'operation_type': 1,
            }
        )
        self._insert(
            {
                'id': 1,
                'transaction_id': 2,
                'end_transaction_id': 4,
                'name': u'Article 1',
                'name_mod': False,
                'operation_type': 2,
            }
        )
        self._insert(
            {
                'id': 2,
                'transaction_id': 3,
                'end_transaction_id': 5,
                'name': u'Article 2',
                'name_mod': False,
                'operation_type': 1,
            }
        )
        self._insert(
            {
                'id': 1,
                'transaction_id': 4,
                'end_transaction_id': None,
                'name': u'Article 1 updated',
                'name_mod': False,
                'operation_type': 2,
            }
        )
        self._insert(
            {
                'id': 2,
                'transaction_id': 5,
                'end_transaction_id': None,
                'name': u'Article 2',
                'name_mod': False,
                'operation_type': 2,
            }
        )

        update_property_mod_flags(
            table,
            ['name'],
            conn=self.session
        )
        rows = self.session.execute(
            'SELECT * FROM article_version ORDER BY transaction_id'
        ).fetchall()
        assert rows[0].transaction_id == 1
        assert rows[0].name_mod
        assert rows[1].transaction_id == 2
        assert not rows[1].name_mod
        assert rows[2].transaction_id == 3
        assert rows[2].name_mod
        assert rows[3].transaction_id == 4
        assert rows[3].name_mod
        assert rows[4].transaction_id == 5
        assert not rows[4].name_mod
