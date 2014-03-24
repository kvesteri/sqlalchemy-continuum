from copy import copy

import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from sqlalchemy_continuum.plugins import PropertyModTrackerPlugin
from tests import TestCase


def update_property_mod_flags(
    table_name,
    tracked_columns,
    mod_suffix='_mod',
    primary_keys=['id'],
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id',
    op=None
):
    if op is None:
        from alembic import op

    query = '''SELECT
            {primary_keys},
            v.{tx_column_name},
            {tracked_columns}
        FROM {table_name} AS v
        LEFT JOIN {table_name} AS v2
            ON
            v2.{end_tx_column_name} = v.{tx_column_name}
            AND
            {pk_condition}
        ORDER BY v.{tx_column_name}
    '''.format(
        table_name=table_name,
        tx_column_name=tx_column_name,
        tracked_columns=', '.join(
            '(v.%s != v2.%s OR v2.transaction_id IS NULL) AS %s%s' % (
                column, column, column, mod_suffix
            )
            for column in tracked_columns
        ),
        end_tx_column_name=end_tx_column_name,
        primary_keys=', '.join('v.%s' % pk for pk in primary_keys),
        pk_condition=' AND '.join(
            'v.%s == v2.%s' % (pk, pk) for pk in primary_keys
        )
    )

    stmt = op.execute(query)

    for row in stmt:
        values = [
            '%s = %s' % (column + mod_suffix, row[column + mod_suffix])
            for column in tracked_columns
            if row[column + mod_suffix]
        ]
        if values:
            query = '''UPDATE
                {table_name}
                SET {values}
                WHERE
                    {condition}
            '''.format(
                table_name=table_name,
                values=', '.join(values),
                condition=' AND '.join(
                    '%s = %s' % (pk, row[pk]) for pk in primary_keys
                ) + ' AND transaction_id = %s' % row[tx_column_name]
            )
            op.execute(query)


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

    def test_something(self):
        table = version_class(self.Article).__table__
        stmt = table.insert().values([
            {
                'id': 1,
                'transaction_id': 1,
                'end_transaction_id': 2,
                'name': u'Article 1',
                'name_mod': False,
                'operation_type': 1,
            },
            {
                'id': 1,
                'transaction_id': 2,
                'end_transaction_id': 4,
                'name': u'Article 1',
                'name_mod': False,
                'operation_type': 2,
            },
            {
                'id': 2,
                'transaction_id': 3,
                'end_transaction_id': 5,
                'name': u'Article 2',
                'name_mod': False,
                'operation_type': 1,
            },
            {
                'id': 1,
                'transaction_id': 4,
                'end_transaction_id': None,
                'name': u'Article 1 updated',
                'name_mod': False,
                'operation_type': 2,
            },
            {
                'id': 2,
                'transaction_id': 5,
                'end_transaction_id': None,
                'name': u'Article 2',
                'name_mod': False,
                'operation_type': 2,
            },
        ])
        self.session.execute(stmt)

        update_property_mod_flags(
            'article_version',
            ['name'],
            op=self.session
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
