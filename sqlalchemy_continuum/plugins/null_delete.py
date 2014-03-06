from .base import Plugin
from ..operation import Operation
from ..utils import versioned_columns


class NullDeletePlugin(Plugin):
    def should_nullify_column(self, version_obj, column):
        """
        Return whether or not given column of given version object should
        be nullified (set to None) at the end of the transaction.

        :param version_obj:
            Version object to check the attribute nullification
        :paremt attr:
            SQLAlchemy ColumnProperty object
        """
        return (
            version_obj.operation_type == Operation.DELETE and
            not column.primary_key and
            column.key !=
            self.manager.option(
                version_obj,
                'transaction_column_name'
            )
        )

    def after_create_history_object(self, uow, parent_obj, version_obj):
        for prop in versioned_columns(parent_obj):
            if self.should_nullify_column(version_obj, prop):
                setattr(version_obj, prop.key, None)
