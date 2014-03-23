from sqlalchemy_continuum import version_class
from tests import TestCase


def update_end_transaction_column(
    table_name,
    primary_keys=['id'],
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id',
    op=None
):
    if op is None:
        from alembic import op

    stmt = op.execute(
        '''SELECT
            {primary_keys},
            v.{tx_column_name},
            v2.{tx_column_name} AS end_transaction_id
        FROM {table_name} AS v
        LEFT JOIN {table_name} AS v2
            ON
            v2.{tx_column_name} = (
                SELECT MIN(v3.{tx_column_name})
                FROM {table_name} v3
                WHERE
                    {pk_condition}
                    AND
                    v3.{tx_column_name} > v.{tx_column_name}
            )
        ORDER BY v.{tx_column_name}
        '''
        .format(
            table_name=table_name,
            tx_column_name=tx_column_name,
            primary_keys=', '.join('v.%s' % pk for pk in primary_keys),
            pk_condition=' AND '.join(
                'v.%s == v3.%s' % (pk, pk) for pk in primary_keys
            )
        )
    )
    for row in stmt:
        if row['end_transaction_id']:
            op.execute(
                '''UPDATE
                {table_name}
                SET {end_tx_column_name} = {end_tx_value}
                WHERE
                    {condition}
                '''
                .format(
                    table_name=table_name,
                    end_tx_column_name=end_tx_column_name,
                    end_tx_value=row['end_transaction_id'],
                    condition=' AND '.join(
                        '%s = %s' % (pk, row[pk]) for pk in primary_keys
                    ) + ' AND transaction_id = %s' % row[tx_column_name]
                )
            )


class TestSchemaTools(TestCase):
    versioning_strategy = 'validity'

    def test_something(self):
        table = version_class(self.Article).__table__
        stmt = table.insert().values([
            {
                'id': 1,
                'transaction_id': 1,
                'name': u'Article 1',
                'operation_type': 1,
            },
            {
                'id': 1,
                'transaction_id': 2,
                'name': u'Article 1 updated',
                'operation_type': 2,
            },
            {
                'id': 2,
                'transaction_id': 3,
                'name': u'Article 2',
                'operation_type': 1,
            },
            {
                'id': 1,
                'transaction_id': 4,
                'name': u'Article 1 updated (again)',
                'operation_type': 2,
            },
            {
                'id': 2,
                'transaction_id': 5,
                'name': u'Article 2 updated',
                'operation_type': 2,
            },
        ])
        self.session.execute(stmt)

        update_end_transaction_column('article_version', op=self.session)
        rows = self.session.execute(
            'SELECT * FROM article_version ORDER BY transaction_id'
        ).fetchall()
        assert rows[0].transaction_id == 1
        assert rows[0].end_transaction_id == 2
        assert rows[1].transaction_id == 2
        assert rows[1].end_transaction_id == 4
        assert rows[2].transaction_id == 3
        assert rows[2].end_transaction_id == 5
        assert rows[3].transaction_id == 4
        assert rows[3].end_transaction_id is None
        assert rows[4].transaction_id == 5
        assert rows[4].end_transaction_id is None
