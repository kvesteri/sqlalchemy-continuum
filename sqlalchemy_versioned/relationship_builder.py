import sqlalchemy as sa
from sqlalchemy.sql.expression import (
    BooleanClauseList,
    BinaryExpression,
    BindParameter
)
from .builder import VersionedBuilder


class VersionedRelationshipBuilder(VersionedBuilder):
    def reflect_expression(self, expression):
        if expression is None:
            return
        if isinstance(expression, BinaryExpression):
            return self.reflect_binary_expression(expression)
        elif isinstance(expression, BooleanClauseList):
            return self.reflect_boolean_expression(expression)

    def reflect_expression_parameter(self, parameter):
        if isinstance(parameter, sa.Column):
            table = self.model.metadata.tables[
                parameter.table.name + '_history'
            ]
            return table.c[parameter.name]
        elif isinstance(parameter, BindParameter):
            return parameter

    def reflect_binary_expression(self, expression):
        return expression.operator(
            self.reflect_expression_parameter(expression.left),
            self.reflect_expression_parameter(expression.right)
        )

    def reflect_boolean_expression(self, expression):
        return expression.operator(*[
            self.reflect_expression(child_expr)
            for child_expr in expression.get_children()
        ])

    def relationship_foreign_keys(self, property_):
        remote_cls = property_.mapper.class_.__versioned__['class']
        if property_.secondary is None:
            return [
                getattr(remote_cls, pair[1].name)
                for pair in property_.local_remote_pairs
            ]

    def relationship_secondary(self, property_):
        if property_.secondary is not None:
            return property_.secondary.name + '_history'

    def transaction_table_correlation(self, local_cls, remote_cls):
        return (
            remote_cls.transaction_id == sa.select(
                [sa.func.max(remote_cls.transaction_id)]
            ).where(
                remote_cls.transaction_id <= local_cls.transaction_id
            ).correlate(local_cls.__table__)
        )

    def relationship_kwargs(self, property_):
        local_cls = self.model.__versioned__['class']
        remote_cls = property_.mapper.class_.__versioned__['class']

        return dict(
            primaryjoin=sa.and_(
                self.reflect_expression(
                    property_.primaryjoin
                ),
                self.transaction_table_correlation(local_cls, remote_cls)
            ),
            foreign_keys=self.relationship_foreign_keys(
                property_
            ),
            secondaryjoin=self.reflect_expression(
                property_.secondaryjoin
            ),
            secondary=self.relationship_secondary(property_),
            viewonly=True
        )

    def build_reflected_relationships(self):
        for attr in self.attrs:
            if attr.key == 'versions':
                continue
            property_ = attr.property
            if isinstance(property_, sa.orm.RelationshipProperty):
                local_cls = self.model.__versioned__['class']
                remote_cls = property_.mapper.class_.__versioned__['class']

                setattr(
                    local_cls,
                    attr.key,
                    sa.orm.relationship(
                        remote_cls,
                        **self.relationship_kwargs(property_)
                    )
                )
