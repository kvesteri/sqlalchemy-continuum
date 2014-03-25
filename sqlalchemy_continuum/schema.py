import sqlalchemy as sa


def get_end_tx_column_query(
    table,
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id'
):

    v1 = sa.alias(table, name='v')
    v2 = sa.alias(table, name='v2')
    v3 = sa.alias(table, name='v3')

    primary_keys = [c.name for c in table.c if c.primary_key]

    tx_criterion = sa.select(
        [sa.func.min(getattr(v3.c, tx_column_name))]
    ).where(
        sa.and_(
            getattr(v3.c, tx_column_name) > getattr(v1.c, tx_column_name),
            *[
                getattr(v3.c, pk) == getattr(v1.c, pk)
                for pk in primary_keys
                if pk != tx_column_name
            ]
        )
    )
    return sa.select(
        columns=[
            getattr(v1.c, column)
            for column in primary_keys
        ] + [
            getattr(v2.c, tx_column_name).label(end_tx_column_name)
        ],
        from_obj=v1.outerjoin(
            v2,
            sa.and_(
                getattr(v2.c, tx_column_name) ==
                tx_criterion
            )
        )
    ).order_by(getattr(v1.c, tx_column_name))


def update_end_tx_column(
    table,
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id',
    op=None
):
    if op is None:
        from alembic import op

    query = get_end_tx_column_query(
        table,
        end_tx_column_name=end_tx_column_name,
        tx_column_name=tx_column_name
    )
    stmt = op.execute(query)
    primary_keys = [c.name for c in table.c if c.primary_key]
    for row in stmt:
        if row[end_tx_column_name]:
            criteria = [
                getattr(table.c, pk) == row[pk]
                for pk in primary_keys
            ]

            update_stmt = (
                table.update()
                .where(sa.and_(*criteria))
                .values({end_tx_column_name: row[end_tx_column_name]})
            )
            op.execute(update_stmt)


def get_property_mod_flags_query(
    table,
    tracked_columns,
    mod_suffix='_mod',
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id',
):
    v1 = sa.alias(table, name='v')
    v2 = sa.alias(table, name='v2')
    primary_keys = [c.name for c in table.c if c.primary_key]

    return sa.select(
        columns=[
            getattr(v1.c, column)
            for column in primary_keys
        ] + [
            (sa.or_(
                getattr(v1.c, column) != getattr(v2.c, column),
                getattr(v2.c, tx_column_name).is_(None)
            )).label(column + mod_suffix)
            for column in tracked_columns
        ],
        from_obj=v1.outerjoin(
            v2,
            sa.and_(
                getattr(v2.c, end_tx_column_name) ==
                getattr(v1.c, tx_column_name),
                *[
                    getattr(v2.c, pk) == getattr(v1.c, pk)
                    for pk in primary_keys
                    if pk != tx_column_name
                ]
            )
        )
    ).order_by(getattr(v1.c, tx_column_name))


def update_property_mod_flags(
    table,
    tracked_columns,
    mod_suffix='_mod',
    end_tx_column_name='end_transaction_id',
    tx_column_name='transaction_id',
    op=None
):
    if op is None:
        from alembic import op

    query = get_property_mod_flags_query(
        table,
        tracked_columns,
        mod_suffix=mod_suffix,
        end_tx_column_name=end_tx_column_name,
        tx_column_name=tx_column_name,
    )
    stmt = op.execute(query)

    primary_keys = [c.name for c in table.c if c.primary_key]
    for row in stmt:
        values = dict([
            (column + mod_suffix, row[column + mod_suffix])
            for column in tracked_columns
            if row[column + mod_suffix]
        ])
        if values:
            criteria = [
                getattr(table.c, pk) == row[pk] for pk in primary_keys
            ]
            query = table.update().where(sa.and_(*criteria)).values(values)
            op.execute(query)
