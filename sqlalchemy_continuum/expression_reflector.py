from sqlalchemy.sql.expression import bindparam

from sqlalchemy_utils import ExpressionParser
from .utils import version_table


class VersionExpressionParser(ExpressionParser):

    def column(self, column):
        try:
            table = version_table(column.table)
        except KeyError:
            return column
        else:
            return table.c[column.name]


class VersionExpressionReflector(VersionExpressionParser):
    def __init__(self, parent, relationship):
        self.parent = parent
        self.relationship = relationship

    def column(self, column):
        try:
            table = version_table(column.table)
        except KeyError:
            reflected_column = column
        else:
            reflected_column = table.c[column.name]
            if column in self.relationship.local_columns and \
               table == self.parent.__table__:
                    reflected_column = bindparam(column.key,
                                        getattr(self.parent, column.key))

        return reflected_column

