import sqlalchemy as sa
from sqlalchemy_utils import primary_keys


class VersionClassBase(object):
    @property
    def previous(self):
        """
        Returns the previous version relative to this version in the version
        history. If current version is the first version this method returns
        None.
        """
        if not self.parent:
            # parent object has been deleted
            return self._previous_query.first()
        if self.index > 0:
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
        pks = (
            [pk.name for pk in primary_keys(self.__parent_class__)] +
            ['transaction_id']
        )

        for column_name in pks:
            if skip_transaction_id and column_name == 'transaction_id':
                continue
            conditions.append(
                getattr(self, column_name)
                ==
                getattr(self.__class__, column_name)
            )
        return conditions

    @property
    def next(self):
        """
        Returns the next version relative to this version in the version
        history. If current version is the last version this method returns
        None.
        """
        if not self.parent:
            # parent object has been deleted
            return self._next_query.first()
        if self.index < (self.parent.versions.count() - 1):
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

    @property
    def changeset(self):
        data = {}
        class_manager = self.__mapper__.class_manager
        previous_version = self.previous
        if not previous_version and self.operation_type != 0:
            return {}

        for key, attr in class_manager.items():
            if key in ['transaction_id', 'operation_type']:
                continue
            if isinstance(attr.property, sa.orm.ColumnProperty):
                if not previous_version:
                    old = None
                else:
                    old = getattr(previous_version, key)
                new = getattr(self, key)
                if old != new:
                    data[key] = [
                        old,
                        new
                    ]
        return data

    def reify(self, visited_objects=[]):
        if self in visited_objects:
            return

        session = sa.orm.object_session(self)

        if self.operation_type == 2:
            session.delete(self.parent)
            return

        visited_objects.append(self)
        parent_mapper = self.__parent_class__.__mapper__

        # Check if parent object has been deleted
        if self.parent is None:
            self.parent = self.__parent_class__()
            session.add(self.parent)

        # Before reifying relations we need to reify object properties. This
        # is needed because reifying relations might need to flush the session
        # which leads to errors when sqlalchemy tries to insert null values
        # into parent object (if parent object has not null constraints).
        for key, attr in parent_mapper.class_manager.items():
            if isinstance(attr.property, sa.orm.ColumnProperty):
                if key != 'transaction_id':
                    setattr(self.parent, key, getattr(self, key))

        for key, attr in parent_mapper.class_manager.items():
            if isinstance(attr.property, sa.orm.RelationshipProperty):
                if key not in ['versions', 'transaction']:
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

        return self.parent
