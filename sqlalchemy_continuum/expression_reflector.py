from sqlalchemy.sql.expression import bindparam

from sqlalchemy_utils import ExpressionParser
from .utils import version_table


class VersionExpressionParser(ExpressionParser):
    parent = None
    parent_class = None

    def column(self, column):
        try:
            table = version_table(column.table)
        except KeyError:
            return column
        if self.parent and table == self.parent.__table__:
            return bindparam(column.key, getattr(self.parent, column.key))
        else:
            return table.c[column.name]


class VersionExpressionReflector(VersionExpressionParser):
    def __init__(self, parent):
        self.parent = parent
