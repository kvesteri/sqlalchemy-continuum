import operator
import sqlalchemy as sa
from sqlalchemy_utils import primary_keys
from .utils import tx_column_name, end_tx_column_name


class HistoryObjectFetcher(object):
    def __init__(self, manager):
        self.manager = manager

    def previous(self, obj):
        """
        Returns the previous version relative to this version in the version
        history. If current version is the first version this method returns
        None.
        """
        return self.previous_query(obj).first()

    def index(self, obj):
        """
        Return the index of this version in the version history.
        """
        session = sa.orm.object_session(obj)
        return session.execute(self._index_query(obj)).fetchone()[0]

    def next(self, obj):
        """
        Returns the next version relative to this version in the version
        history. If current version is the last version this method returns
        None.
        """
        return self.next_query(obj).first()

    def _pk_correlation_condition(self, obj, skip_transaction_id=True):
        conditions = []
        pks = (
            [pk.name for pk in primary_keys(obj.__parent_class__)] +
            [tx_column_name(obj)]
        )

        for column_name in pks:
            if (
                skip_transaction_id and
                column_name == tx_column_name(obj)
            ):
                continue
            conditions.append(
                getattr(obj, column_name)
                ==
                getattr(obj.__class__, column_name)
            )
        return conditions

    def _transaction_id_subquery(self, obj, next_or_prev='next'):
        if next_or_prev == 'next':
            op = operator.gt
            func = sa.func.min
        else:
            op = operator.lt
            func = sa.func.max

        alias = sa.orm.aliased(obj)

        return (
            sa.select(
                [func(
                    getattr(alias, tx_column_name(obj))
                )],
                from_obj=[alias.__table__]
            )
            .where(
                op(
                    getattr(alias, tx_column_name(obj)),
                    getattr(obj, tx_column_name(obj))
                )
            )
            .correlate(alias.__table__)
        )

    def _next_prev_query(self, obj, next_or_prev='next'):
        session = sa.orm.object_session(obj)

        return (
            session.query(obj.__class__)
            .filter(
                sa.and_(
                    getattr(
                        obj.__class__,
                        tx_column_name(obj)
                    )
                    ==
                    self._transaction_id_subquery(
                        obj, next_or_prev=next_or_prev
                    ),
                    *self._pk_correlation_condition(obj)
                )
            )
        )

    def _index_query(self, obj):
        """
        Returns the query needed for fetching the index of this record relative
        to version history.
        """
        alias = sa.orm.aliased(obj)

        subquery = (
            sa.select([sa.func.count('1')], from_obj=[alias.__table__])
            .where(
                getattr(alias, tx_column_name(obj))
                <
                getattr(obj, tx_column_name(obj))
            )
            .correlate(alias.__table__)
            .label('position')
        )
        query = (
            sa.select([subquery], from_obj=[obj.__table__])
            .where(sa.and_(*self._pk_correlation_condition(obj, False)))
            .order_by(
                getattr(obj.__class__, tx_column_name(obj))
            )
        )
        return query


class SubqueryFetcher(HistoryObjectFetcher):
    def previous_query(self, obj):
        """
        Returns the query that fetches the previous version relative to this
        version in the version history.
        """
        return self._next_prev_query(obj, 'previous')

    def next_query(self, obj):
        """
        Returns the query that fetches the next version relative to this
        version in the version history.
        """
        return self._next_prev_query(obj, 'next')


class ValidityFetcher(HistoryObjectFetcher):
    def next_query(self, obj):
        """
        Returns the query that fetches the next version relative to this
        version in the version history.
        """
        session = sa.orm.object_session(obj)

        return (
            session.query(obj.__class__)
            .filter(
                sa.and_(
                    getattr(
                        obj.__class__,
                        tx_column_name(obj)
                    )
                    ==
                    getattr(
                        obj,
                        end_tx_column_name(obj)
                    ),
                    *self._pk_correlation_condition(obj)
                )
            )
        )

    def previous_query(self, obj):
        """
        Returns the query that fetches the previous version relative to this
        version in the version history.
        """
        session = sa.orm.object_session(obj)

        return (
            session.query(obj.__class__)
            .filter(
                sa.and_(
                    getattr(
                        obj.__class__,
                        end_tx_column_name(obj)
                    )
                    ==
                    getattr(obj, tx_column_name(obj)),
                    *self._pk_correlation_condition(obj)
                )
            )
        )
