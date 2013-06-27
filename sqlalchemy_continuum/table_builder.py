import sqlalchemy as sa
from .builder import VersionedBuilder


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
        return self.option('table_name') % self.parent_table.name

    def build_reflected_columns(self):
        columns = []
        excluded_column_names = self.option('exclude')

        for column in self.parent_table.c:
            if self.model and column.name in excluded_column_names:
                continue
            # Make a copy of the column so that it does not point to wrong
            # table.
            column_copy = column.copy()
            # Remove unique constraints
            column_copy.unique = False
            column_copy.autoincrement = False
            if column_copy.name == 'revision':
                column_copy.nullable = False

            if not column_copy.primary_key:
                column_copy.nullable = True

            columns.append(column_copy)

        # When using join table inheritance each table should have revision
        # column.
        if 'revision' not in [c.name for c in columns]:
            columns.append(sa.Column('revision', sa.Integer))

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
            primary_key=True
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
