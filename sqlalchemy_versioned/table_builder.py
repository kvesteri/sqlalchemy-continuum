import sqlalchemy as sa
from .builder import VersionedBuilder


class VersionedTableBuilder(VersionedBuilder):
    @property
    def table_name(self):
        return self.option('table_name') % self.model.__tablename__

    def build_reflected_columns(self):
        columns = []
        for attr in self.attrs:
            if not isinstance(attr.property, sa.orm.ColumnProperty):
                continue
            column = attr.property.columns[0]
            # Make a copy of the column so that it does not point to wrong
            # table.
            column_copy = column.copy()
            # Remove unique constraints
            column_copy.unique = False
            columns.append(column_copy)
        return columns

    def build_transaction_table_foreign_key(self):
        return sa.schema.ForeignKeyConstraint(
            [self.option('version_column_name')],
            ['transaction_log.id'],
            ondelete='CASCADE'
        )

    def build_version_column(self):
        return sa.Column(
            self.option('version_column_name'),
            sa.BigInteger,
            primary_key=True
        )

    def build_table(self, extends=None):
        items = []
        if extends is None:
            items.extend(self.build_reflected_columns())
            items.append(self.build_version_column())

        if extends is None:
            items.append(self.build_transaction_table_foreign_key())

        return sa.schema.Table(
            extends.name if extends is not None else self.table_name,
            self.model.__bases__[0].metadata,
            *items,
            extend_existing=extends is not None
        )
