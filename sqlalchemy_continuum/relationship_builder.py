import sqlalchemy as sa
from .table_builder import TableBuilder
from .expression_reflector import ObjectExpressionReflector
from .operation import Operation
from .utils import version_table, version_class


class RelationshipBuilder(object):
    def __init__(self, versioning_manager, model, property_):
        self.manager = versioning_manager
        self.property = property_
        self.model = model

    def option(self, name):
        return self.manager.option(self.model, name)

    def relationship_subquery(self, obj):
        primary_keys = []

        column_name = self.option('transaction_column_name')

        for column in self.remote_cls.__table__.c:
            if column.primary_key and column.name != column_name:
                primary_keys.append(column)

        return getattr(self.remote_cls, column_name).in_(
            sa.select(
                [sa.func.max(getattr(self.remote_cls, column_name))]
            ).where(
                getattr(self.remote_cls, column_name) <=
                getattr(obj, column_name)
            ).group_by(
                *primary_keys
            ).correlate(self.local_cls)
        )

    @property
    def reflected_relationship(self):
        """
        Builds a reflected one-to-many, one-to-one and many-to-one
        relationship between two version classes.
        """
        @property
        def relationship(obj):
            session = sa.orm.object_session(obj)
            reflector = ObjectExpressionReflector(obj)
            return (
                session.query(self.remote_cls)
                .filter(
                    sa.and_(
                        reflector(self.property.primaryjoin),
                        self.relationship_subquery(obj),
                        self.remote_cls.operation_type != Operation.DELETE
                    )
                )
            )
        return relationship

    def association_subquery(self, obj):
        """
        Returns association subquery for given SQLAlchemy declarative object.

        :param obj: SQLAlchemy declarative object
        """
        column_name = self.option('transaction_column_name')
        reflector = ObjectExpressionReflector(obj)
        subquery = (
            getattr(self.remote_table.c, column_name).in_(
                sa.select(
                    [sa.func.max(getattr(self.remote_table.c, column_name))],
                ).where(
                    sa.and_(
                        getattr(self.remote_table.c, column_name) <=
                        getattr(obj, column_name),
                        reflector(self.property.primaryjoin)
                    )
                ).group_by(
                    self.remote_table.c[self.remote_column.name]
                ).correlate(self.local_cls)
            )
        )

        return (
            sa.select(
                [self.remote_table.c[self.remote_column.name]]
            ).where(
                sa.and_(
                    subquery,
                    self.remote_table.c.operation_type != Operation.DELETE
                )
            )
        )

    @property
    def reflected_association(self):
        """
        Builds a reflected many-to-many relationship between two version
        classes.
        """
        column_name = self.option('transaction_column_name')

        @property
        def relationship(obj):
            session = sa.orm.object_session(obj)

            condition = (
                getattr(self.remote_cls, column_name) == sa.select(
                    [sa.func.max(getattr(self.remote_cls, column_name))]
                ).where(
                    getattr(self.remote_cls, column_name) <=
                    getattr(obj, column_name)
                ).correlate(self.local_cls)
            )
            return (
                session.query(self.remote_cls)
                .filter(
                    sa.and_(
                        self.remote_cls.id.in_(self.association_subquery(obj)),
                        condition
                    )
                )
            )
        return relationship

    def build_association_version_tables(self):
        """
        Builds many-to-many association version table for given property.
        Association version tables are used for tracking change history of
        many-to-many associations.
        """
        column = list(self.property.remote_side)[0]

        self.manager.association_tables.add(column.table)
        builder = TableBuilder(
            self.manager,
            column.table
        )
        metadata = column.table.metadata
        if metadata.schema:
            table_name = metadata.schema + '.' + builder.table_name
        else:
            table_name = builder.table_name

        if table_name not in metadata.tables:
            table = builder()

            self.manager.association_version_tables.add(table)

    def __call__(self):
        """
        Builds reflected relationship between version classes based on given
        parent object's RelationshipProperty.
        """
        self.local_cls = version_class(self.model)
        try:
            self.remote_cls = version_class(self.property.mapper.class_)
        except (AttributeError, KeyError):
            return

        reflection_func = 'reflected_relationship'
        if self.property.secondary is not None:
            self.build_association_version_tables()

            for column_pair in self.property.local_remote_pairs:
                if column_pair[0] in self.property.table.c.values():
                    self.remote_column = column_pair[1]
                    break

            self.remote_table = version_table(self.remote_column.table)
            reflection_func = 'reflected_association'
        setattr(
            self.local_cls,
            self.property.key,
            getattr(self, reflection_func)
        )
