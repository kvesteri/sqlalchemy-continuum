import sqlalchemy as sa


class VersionClassBase(object):
    @property
    def previous(self):
        """
        Returns the previous version relative to this version in the version
        history. If current version is the first version this method returns
        None.
        """
        return self.__versioning_manager__.fetcher(self).previous(self)

    @property
    def next(self):
        """
        Returns the next version relative to this version in the version
        history. If current version is the last version this method returns
        None.
        """
        return self.__versioning_manager__.fetcher(self).next(self)

    @property
    def index(self):
        """
        Return the index of this version in the version history.
        """
        return self.__versioning_manager__.fetcher(self).index(self)

    @property
    def changeset(self):
        """
        Return a dictionary of changed fields in this version with keys as
        field names and values as lists with first value as the old field value
        and second list value as the new value.
        """
        data = {}
        class_manager = self.__mapper__.class_manager
        previous_version = self.previous
        if not previous_version and self.operation_type != 0:
            return {}

        for key, attr in class_manager.items():
            if key in [
                self.__versioning_manager__.option(
                    self.__parent_class__, 'transaction_column_name'
                ),
                'operation_type'
            ]:
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
            session.delete(self.version_parent)
            return

        visited_objects.append(self)
        parent_mapper = self.__parent_class__.__mapper__

        # Check if parent object has been deleted
        if self.version_parent is None:
            self.version_parent = self.__parent_class__()
            session.add(self.version_parent)

        # Before reifying relations we need to reify object properties. This
        # is needed because reifying relations might need to flush the session
        # which leads to errors when sqlalchemy tries to insert null values
        # into parent object (if parent object has not null constraints).
        for key, attr in parent_mapper.class_manager.items():
            if isinstance(attr.property, sa.orm.ColumnProperty):
                if key != 'transaction_id':
                    setattr(self.version_parent, key, getattr(self, key))

        for key, attr in parent_mapper.class_manager.items():
            if isinstance(attr.property, sa.orm.RelationshipProperty):
                if key not in ['versions', 'transaction']:
                    if attr.property.secondary is not None:
                        setattr(self.version_parent, key, [])
                        for value in getattr(self, key):
                            value = value.reify()
                            if value:
                                getattr(self.version_parent, key).append(
                                    value
                                )
                    else:
                        for value in getattr(self, key):
                            value.reify(visited_objects)

        return self.version_parent
