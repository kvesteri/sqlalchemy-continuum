import sqlalchemy as sa
from .reverter import Reverter


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

    def revert(self, relations=[]):
        return Reverter(self, relations=relations)()
