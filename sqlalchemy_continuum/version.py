import sqlalchemy as sa
from sqlalchemy_utils import primary_keys


class VersionClassBase(object):
    @property
    def previous(self):
        """
        Returns the previous version relative to this version in the version
        history.
        """
        if not self.parent:
            # parent object has been deleted
            return self._previous_query.first()
        return self.parent.versions[self.index - 1]

    @property
    def _previous_query(self):
        """
        Returns the query that fetches the previous version relative to this
        version in the version history.
        """
        session = sa.orm.object_session(self)
        alias = sa.orm.aliased(self)
        subquery = (
            sa.select(
                [sa.func.max(alias.transaction_id)],
                from_obj=[alias.__table__]
            )
            .where(alias.transaction_id < self.transaction_id)
            .correlate(alias.__table__)
        )
        return (
            session.query(self.__class__)
            .filter(sa.and_(*self._pk_correlation_condition()))
            .filter(self.__class__.transaction_id == subquery)
        )

    def _pk_correlation_condition(self, skip_transaction_id=True):
        conditions = []
        for primary_key in primary_keys(self):
            if skip_transaction_id and primary_key.name == 'transaction_id':
                continue
            conditions.append(
                getattr(self, primary_key.name)
                ==
                getattr(self.__class__, primary_key.name)
            )
        return conditions

    @property
    def next(self):
        """
        Returns the next version relative to this version in the version
        history.
        """
        if not self.parent:
            # parent object has been deleted
            return self._next_query.first()
        return self.parent.versions[self.index + 1]

    @property
    def _next_query(self):
        """
        Returns the query that fetches the next version relative to this
        version in the version history.
        """
        session = sa.orm.object_session(self)

        alias = sa.orm.aliased(self)
        subquery = (
            sa.select(
                [sa.func.min(alias.transaction_id)],
                from_obj=[alias.__table__]
            )
            .where(alias.transaction_id > self.transaction_id)
            .correlate(alias.__table__)
        )
        return (
            session.query(self.__class__)
            .filter(sa.and_(*self._pk_correlation_condition()))
            .filter(self.__class__.transaction_id == subquery)
        )

    @property
    def _index_query(self):
        """
        Returns the query needed for fetching the index of this record relative
        to version history.
        """
        alias = sa.orm.aliased(self)
        subquery = (
            sa.select([sa.func.count('1')], from_obj=[alias.__table__])
            .where(alias.transaction_id < self.transaction_id)
            .correlate(alias.__table__)
            .label('position')
        )
        query = (
            sa.select([subquery], from_obj=[self.__table__])
            .where(sa.and_(*self._pk_correlation_condition(False)))
            .order_by(self.__class__.transaction_id)
        )
        return query

    @property
    def index(self):
        """
        Return the index of this version in the version history.
        """
        if not self.parent:
            # parent object has been deleted
            session = sa.orm.object_session(self)
            return session.execute(self._index_query).fetchone()[0]

        for index_, version in enumerate(self.parent.versions):
            if version == self:
                return index_

    def reify(self, visited_objects=[]):
        if self in visited_objects:
            return
        visited_objects.append(self)
        parent_mapper = self.__parent_class__.__mapper__

        # Check if parent object has been deleted
        if self.parent is None:
            self.parent = self.__parent_class__()

        for key, attr in parent_mapper.class_manager.items():
            if key not in ['versions', 'transaction', 'transaction_id']:
                if isinstance(attr.property, sa.orm.RelationshipProperty):
                    if attr.property.secondary is not None:
                        setattr(self.parent, key, [])
                        for value in getattr(self, key):
                            value = value.reify()
                            if value:
                                getattr(self.parent, key).append(
                                    value
                                )
                    else:
                        for value in getattr(self, key):
                            value.reify(visited_objects)
                else:
                    setattr(self.parent, key, getattr(self, key))
        return self.parent
