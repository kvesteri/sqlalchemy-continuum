import sqlalchemy as sa
from sqlalchemy.sql.expression import bindparam

from .utils import version_table


class VersionExpressionReflector(sa.sql.visitors.ReplacingCloningVisitor):
    """Take an expression and convert the columns to the version_table's columns"""
    def replace(self, column):
        if not isinstance(column, sa.Column):
            return
        try:
            table = version_table(column.table)
        except KeyError:
            reflected_column = column
        else:
            reflected_column = table.c[column.name]

        return reflected_column

    def __call__(self, expr):
        return self.traverse(expr)


class RelationshipPrimaryJoinReflector(VersionExpressionReflector):
    """
    Takes a relationship and modifies it to handle the primaryjoin of the relationship
    """
    def __init__(self, parent, relationship):
        self.parent = parent
        self.relationship = relationship

    def replace(self, column):
        reflected_column = super().replace(column)
        if reflected_column is None:
            return

        if (
            column in self.relationship.local_columns and
            reflected_column.table == self.parent.__table__
        ):
            # Keep the columns from the self.parent.__table__ as is
            reflected_column = bindparam(
                column.key,
                getattr(self.parent, column.key)
            )

        return reflected_column
