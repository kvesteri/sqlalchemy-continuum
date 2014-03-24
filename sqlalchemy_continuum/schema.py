

def get_end_tx_column_query(
    table_name,
    primary_keys=['id'],
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id'
):
    return '''SELECT
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
    '''.format(
        table_name=table_name,
        tx_column_name=tx_column_name,
        primary_keys=', '.join('v.%s' % pk for pk in primary_keys),
        pk_condition=' AND '.join(
            'v.%s == v3.%s' % (pk, pk) for pk in primary_keys
        )
    )


def update_end_tx_column(
    table_name,
    primary_keys=['id'],
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id',
    op=None
):
    if op is None:
        from alembic import op

    query = get_end_tx_column_query(
        table_name,
        primary_keys=primary_keys,
        end_tx_column_name=end_tx_column_name,
        tx_column_name=tx_column_name
    )
    stmt = op.execute(query)

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


def get_property_mod_flags_query(
    table_name,
    tracked_columns,
    mod_suffix='_mod',
    primary_keys=['id'],
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id',
):
    return '''SELECT
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

    query = get_property_mod_flags_query(
        table_name,
        tracked_columns,
        mod_suffix=mod_suffix,
        primary_keys=primary_keys,
        end_tx_column_name=end_tx_column_name,
        tx_column_name=tx_column_name,
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
