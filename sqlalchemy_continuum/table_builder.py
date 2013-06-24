import sqlalchemy as sa
from .builder import VersionedBuilder


class VersionedTableBuilder(VersionedBuilder):
    def __init__(
        self,
        versioning_manager,
        parent_table,
        remove_primary_keys=False
    ):
        self.manager = versioning_manager
        self.parent_table = parent_table
        self.model = None
        self.remove_primary_keys = remove_primary_keys

    @property
    def table_name(self):
        return self.option('table_name') % self.parent_table.name

    def build_reflected_columns(self):
        columns = []

        for column in self.parent_table.c:
            # Make a copy of the column so that it does not point to wrong
            # table.
            column_copy = column.copy()
            # Remove unique constraints
            column_copy.unique = False
            column_copy.autoincrement = False
            column_copy.nullable = True
            if column_copy.name == 'revision':
                column_copy.primary_key = True
            if self.remove_primary_keys:
                column_copy.primary_key = False
            columns.append(column_copy)
        return columns

    def build_operation_type_column(self):
        return sa.Column(
            self.option('operation_type_column_name'),
            sa.SmallInteger,
            nullable=False
        )

    def build_transaction_column(self):
        return sa.Column(
            self.option('transaction_column_name'),
            sa.BigInteger,
        )

    def build_table(self, extends=None):
        items = []
        if extends is None:
            items.extend(self.build_reflected_columns())
            items.append(self.build_transaction_column())
            items.append(self.build_operation_type_column())
        return sa.schema.Table(
            extends.name if extends is not None else self.table_name,
            self.parent_table.metadata,
            *items,
            extend_existing=extends is not None
        )
