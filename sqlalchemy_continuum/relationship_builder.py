import sqlalchemy as sa
from .table_builder import TableBuilder
from .expression_reflector import ObjectExpressionReflector
from .operation import Operation
from .utils import history_table


class RelationshipBuilder(object):
    def __init__(self, versioning_manager, model, property_):
        self.manager = versioning_manager
        self.property = property_
        self.model = model

    def relationship_subquery(self, obj):
        primary_keys = []
        for column in self.remote_cls.__table__.c:
            if column.primary_key and column.name != 'transaction_id':
                primary_keys.append(column)

        return self.remote_cls.transaction_id.in_(
            sa.select(
                [sa.func.max(self.remote_cls.transaction_id)]
            ).where(
                self.remote_cls.transaction_id <= obj.transaction_id
            ).group_by(
                *primary_keys
            ).correlate(self.local_cls)
        )

    @property
    def reflected_relationship(self):
        """
        Builds a reflected one-to-many, one-to-one and many-to-one
        relationship between two history classes.
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
        reflector = ObjectExpressionReflector(obj)
        subquery = (
            self.remote_table.c.transaction_id.in_(
                sa.select(
                    [sa.func.max(self.remote_table.c.transaction_id)],
                ).where(
                    sa.and_(
                        self.remote_table.c.transaction_id <=
                        obj.transaction_id,
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
        Builds a reflected many-to-many relationship between two history
        classes.
        """
        @property
        def relationship(obj):
            session = sa.orm.object_session(obj)

            condition = (
                self.remote_cls.transaction_id == sa.select(
                    [sa.func.max(self.remote_cls.transaction_id)]
                ).where(
                    self.remote_cls.transaction_id <= obj.transaction_id
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
        Builds many-to-many association history table for given property.
        Association history tables are used for tracking change history of
        many-to-many associations.
        """
        column = list(self.property.remote_side)[0]

        self.manager.association_tables.add(column.table)
        builder = TableBuilder(
            self.manager,
            column.table,
            remove_primary_keys=True
        )
        metadata = column.table.metadata
        if metadata.schema:
            table_name = metadata.schema + '.' + builder.table_name
        else:
            table_name = builder.table_name

        if table_name not in metadata.tables:
            version_table = builder()

            self.manager.association_history_tables.add(
                version_table
            )

    def __call__(self):
        """
        Builds reflected relationship between history classes based on given
        parent object's RelationshipProperty.
        """
        self.local_cls = self.model.__versioned__['class']
        try:
            self.remote_cls = (
                self.property.mapper.class_.__versioned__['class']
            )
        except (AttributeError, KeyError):
            return

        reflection_func = 'reflected_relationship'
        if self.property.secondary is not None:
            self.build_association_version_tables()

            for column_pair in self.property.local_remote_pairs:
                if column_pair[0] in self.property.table.c.values():
                    self.remote_column = column_pair[1]
                    break

            self.remote_table = history_table(self.remote_column.table)
            reflection_func = 'reflected_association'
        setattr(
            self.local_cls,
            self.property.key,
            getattr(self, reflection_func)
        )
