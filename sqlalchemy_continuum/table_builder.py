import sqlalchemy as sa
from sqlalchemy_utils import table_name
from .builder import VersionedBuilder


class VersionedTableBuilder(VersionedBuilder):
    @property
    def table_name(self):
        return self.option('table_name') % table_name(self.model)

    @property
    def parent_columns(self):
        """
        Returns a list of parent table columns.
        """
        return self.model.__table__.c.values()

    def build_reflected_columns(self):
        columns = []

        for column in self.parent_columns:
            # Make a copy of the column so that it does not point to wrong
            # table.
            column_copy = column.copy()
            # Remove unique constraints
            column_copy.unique = False
            column_copy.autoincrement = False
            column_copy.nullable = True
            if column_copy.primary_key:
                column_copy.primary_key = False
            columns.append(column_copy)
        return columns

    def build_revision_column(self):
        return sa.Column(
            self.option('revision_column_name'),
            sa.BigInteger,
            primary_key=True,
            autoincrement=True
        )

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

    @property
    def metadata(self):
        for base in self.model.__bases__:
            if hasattr(base, 'metadata'):
                return base.metadata

        raise Exception(
            'Unable to find base class with appropriate metadata extension'
        )

    def build_table(self, extends=None):
        items = []
        if extends is None:
            items.extend(self.build_reflected_columns())
            items.append(self.build_revision_column())
            items.append(self.build_transaction_column())
            items.append(self.build_operation_type_column())

        return sa.schema.Table(
            extends.name if extends is not None else self.table_name,
            self.metadata,
            *items,
            extend_existing=extends is not None
        )
