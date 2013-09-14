import operator
import sqlalchemy as sa
from sqlalchemy_utils import primary_keys


class HistoryObjectFetcher(object):
    def __init__(self, manager):
        self.manager = manager

    def previous(self, obj):
        """
        Returns the previous version relative to this version in the version
        history. If current version is the first version this method returns
        None.
        """
        return self._previous_query(obj).first()

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
        return self._next_query(obj).first()


class DefaultFetcher(HistoryObjectFetcher):
    def _transaction_id_subquery(self, obj, next_or_prev='next'):
        if next_or_prev == 'next':
            op = operator.gt
            func = sa.func.max
        else:
            op = operator.lt
            func = sa.func.min

        alias = sa.orm.aliased(obj)
        return (
            sa.select(
                [func(alias.transaction_id)],
                from_obj=[alias.__table__]
            )
            .where(op(alias.transaction_id, obj.transaction_id))
            .correlate(alias.__table__)
        )

    def _next_prev_query(self, obj, next_or_prev='next'):
        session = sa.orm.object_session(obj)

        return (
            session.query(obj.__class__)
            .filter(
                sa.and_(
                    obj.__class__.transaction_id ==
                    self._transaction_id_subquery(
                        obj, next_or_prev=next_or_prev
                    ),
                    *self._pk_correlation_condition(obj)
                )
            )
        )

    def _previous_query(self, obj):
        """
        Returns the query that fetches the previous version relative to this
        version in the version history.
        """
        return self._next_prev_query(obj, 'previous')

    def _pk_correlation_condition(self, obj, skip_transaction_id=True):
        conditions = []
        pks = (
            [pk.name for pk in primary_keys(obj.__parent_class__)] +
            ['transaction_id']
        )

        for column_name in pks:
            if skip_transaction_id and column_name == 'transaction_id':
                continue
            conditions.append(
                getattr(obj, column_name)
                ==
                getattr(obj.__class__, column_name)
            )
        return conditions

    def _next_query(self, obj):
        """
        Returns the query that fetches the next version relative to this
        version in the version history.
        """
        return self._next_prev_query(obj, 'next')

    def _index_query(self, obj):
        """
        Returns the query needed for fetching the index of this record relative
        to version history.
        """
        alias = sa.orm.aliased(obj)
        subquery = (
            sa.select([sa.func.count('1')], from_obj=[alias.__table__])
            .where(alias.transaction_id < obj.transaction_id)
            .correlate(alias.__table__)
            .label('position')
        )
        query = (
            sa.select([subquery], from_obj=[obj.__table__])
            .where(sa.and_(*self._pk_correlation_condition(obj, False)))
            .order_by(obj.__class__.transaction_id)
        )
        return query


class ValidityFetcher(HistoryObjectFetcher):
    pass
