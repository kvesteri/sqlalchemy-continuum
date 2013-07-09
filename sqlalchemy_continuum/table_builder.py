import sqlalchemy as sa
from .builder import VersionedBuilder
from .utils import is_auto_assigned_date_column


class VersionedTableBuilder(VersionedBuilder):
    def __init__(
        self,
        versioning_manager,
        parent_table,
        model=None,
        remove_primary_keys=False
    ):
        self.manager = versioning_manager
        self.parent_table = parent_table
        self.model = model
        self.remove_primary_keys = remove_primary_keys

    @property
    def table_name(self):
        """
        Returns the history table name for current parent table.
        """
        return self.option('table_name') % self.parent_table.name

    @property
    def reflected_columns(self):
        """
        Returns reflected parent table columns.

        All columns from parent table are reflected except those that:
        1. Are auto assigned date or datetime columns. Use include option
        parameter if you wish to have these included.
        2. Columns that are part of exclude option parameter.
        """
        columns = []
        excluded_column_names = self.option('exclude')
        included_column_names = self.option('include')

        for column in self.parent_table.c:
            if self.model and column.name in excluded_column_names:
                continue

            if (
                is_auto_assigned_date_column(column) and
                column.name not in included_column_names
            ):
                continue

            # Make a copy of the column so that it does not point to wrong
            # table.
            column_copy = column.copy()
            # Remove unique constraints
            column_copy.unique = False
            column_copy.autoincrement = False
            if column_copy.name == 'transaction_id':
                column_copy.nullable = False

            if not column_copy.primary_key:
                column_copy.nullable = True

            columns.append(column_copy)

        # When using join table inheritance each table should have
        # transaction_id column.
        if 'transaction_id' not in [c.name for c in columns]:
            columns.append(sa.Column('transaction_id', sa.Integer))

        return columns

    @property
    def operation_type_column(self):
        """
        Return the operation type column. By default the name of this column
        is 'operation_type'.
        """
        return sa.Column(
            self.option('operation_type_column_name'),
            sa.SmallInteger,
            nullable=False
        )

    @property
    def transaction_column(self):
        """
        Returns transaction column. By default the name of this column is
        'transaction_id'.
        """
        return sa.Column(
            self.option('transaction_column_name'),
            sa.BigInteger,
            primary_key=True
        )

    def build_table(self, extends=None):
        """
        Builds history table.
        """
        items = []
        if extends is None:
            items.extend(self.reflected_columns)
            items.append(self.transaction_column)
            items.append(self.operation_type_column)
        return sa.schema.Table(
            extends.name if extends is not None else self.table_name,
            self.parent_table.metadata,
            *items,
            extend_existing=extends is not None
        )
