import operator
import sqlalchemy as sa
from sqlalchemy_utils import primary_keys, identity
from .utils import tx_column_name, end_tx_column_name


def eq(tuple_):
    return tuple_[0] == tuple_[1]


def parent_identity(obj_or_class):
    return tuple(
        getattr(obj_or_class, column.name)
        for column in primary_keys(obj_or_class)
        if column.name != tx_column_name(obj_or_class)
    )


class VersionObjectFetcher(object):
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

    def parent_identity_correlation(self, obj):
        return map(
            eq,
            zip(
                parent_identity(obj.__class__),
                parent_identity(obj)
            )
        )

    def _transaction_id_subquery(self, obj, next_or_prev='next'):
        if next_or_prev == 'next':
            op = operator.gt
            func = sa.func.min
        else:
            op = operator.lt
            func = sa.func.max

        alias = sa.orm.aliased(obj)
        query = (
            sa.select(
                [func(
                    getattr(alias, tx_column_name(obj))
                )],
                from_obj=[alias.__table__]
            )
            .where(
                sa.and_(
                    op(
                        getattr(alias, tx_column_name(obj)),
                        getattr(obj, tx_column_name(obj))
                    ),
                    *map(eq, zip(parent_identity(alias), parent_identity(obj)))
                )
            )
            .correlate(alias.__table__)
        )
        return query

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
                    *self.parent_identity_correlation(obj)
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
            .where(
                sa.and_(
                    *map(eq, zip(identity(obj.__class__), identity(obj)))
                )
            )
            .order_by(
                getattr(obj.__class__, tx_column_name(obj))
            )
        )
        return query


class SubqueryFetcher(VersionObjectFetcher):
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


class ValidityFetcher(VersionObjectFetcher):
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
                    getattr(obj.__class__, tx_column_name(obj))
                    ==
                    getattr(obj, end_tx_column_name(obj)),
                    *self.parent_identity_correlation(obj)
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
                    getattr(obj.__class__, end_tx_column_name(obj))
                    ==
                    getattr(obj, tx_column_name(obj)),
                    *self.parent_identity_correlation(obj)
                )
            )
        )
