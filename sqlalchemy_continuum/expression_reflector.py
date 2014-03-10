import six
import sqlalchemy as sa
from sqlalchemy.sql.expression import (
    BooleanClauseList,
    BinaryExpression,
    BindParameter
)
from .utils import version_table


class ExpressionReflector(object):
    parent = None
    parent_class = None

    def expression(self, expression):
        """
        Parses SQLAlchemy expression
        """
        if expression is None:
            return
        if isinstance(expression, BinaryExpression):
            return self.binary_expression(expression)
        elif isinstance(expression, BooleanClauseList):
            return self.boolean_expression(expression)

    def parameter(self, parameter):
        """
        Parses SQLAlchemy BindParameter
        """
        if isinstance(parameter, sa.Column):
            table = version_table(parameter.table)
            if self.parent and table == self.parent.__table__:
                return getattr(self.parent, parameter.name)
            else:
                return table.c[parameter.name]
        elif isinstance(parameter, BindParameter):
            # somehow bind parameters passed as unicode are converted to
            # ascii strings along the way, force convert them back to avoid
            # sqlalchemy unicode warnings
            if isinstance(parameter.type, sa.Unicode):
                parameter.value = six.text_type(parameter.value)
            return parameter

    def binary_expression(self, expression):
        """
        Parses SQLAlchemy BinaryExpression
        """
        return expression.operator(
            self.parameter(expression.left),
            self.parameter(expression.right)
        )

    def boolean_expression(self, expression):
        """
        Parses SQLAlchemy BooleanExpression
        """
        return expression.operator(*[
            self.expression(child_expr)
            for child_expr in expression.get_children()
        ])

    def __call__(self, expression):
        return self.expression(expression)


class ClassExpressionReflector(ExpressionReflector):
    def __init__(self, parent_class):
        self.parent_class = parent_class


class ObjectExpressionReflector(ExpressionReflector):
    def __init__(self, parent):
        self.parent = parent
        self.parent_class = parent.__class__
