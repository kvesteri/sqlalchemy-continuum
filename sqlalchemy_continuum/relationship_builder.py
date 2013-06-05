import sqlalchemy as sa
from sqlalchemy.sql.expression import (
    BooleanClauseList,
    BinaryExpression,
    BindParameter
)
from .builder import VersionedBuilder


class RelationshipExpressionReflector(object):
    def __init__(self, parent):
        self.parent = parent

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
            table = self.parent.__class__.metadata.tables[
                parameter.table.name + '_history'
            ]
            if table == self.parent.__table__:
                return getattr(self.parent, parameter.name)
            else:
                return table.c[parameter.name]
        elif isinstance(parameter, BindParameter):
            # somehow bind parameters passed as unicode are converted to
            # ascii strings along the way, force convert them back to avoid
            # sqlalchemy unicode warnings
            if isinstance(parameter.type, sa.Unicode):
                parameter.value = unicode(parameter.value)
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


class VersionedRelationshipBuilder(VersionedBuilder):
    def reflected_relationship_factory(
        self,
        local_cls,
        remote_cls,
        primary_join
    ):
        @property
        def relationship(obj):
            session = sa.orm.object_session(obj)
            condition = (
                remote_cls.transaction_id == sa.select(
                    [sa.func.max(remote_cls.transaction_id)]
                ).where(
                    remote_cls.transaction_id <= obj.transaction_id
                ).correlate(local_cls)
            )
            reflector = RelationshipExpressionReflector(obj)
            return (
                session.query(remote_cls)
                .filter(
                    sa.and_(
                        reflector(primary_join),
                        condition
                    )
                )
            )
        return relationship

    def build_reflected_relationships(self):
        for attr in self.attrs:
            if attr.key == 'versions':
                continue
            property_ = attr.property
            if isinstance(property_, sa.orm.RelationshipProperty):
                local_cls = self.model.__versioned__['class']
                remote_cls = property_.mapper.class_.__versioned__['class']
                primary_join = property_.primaryjoin

                setattr(
                    local_cls,
                    attr.key,
                    self.reflected_relationship_factory(
                        local_cls, remote_cls, primary_join
                    )
                )
