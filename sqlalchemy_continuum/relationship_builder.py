import sqlalchemy as sa
from .table_builder import TableBuilder
from .expression_reflector import ObjectExpressionReflector
from .operation import Operation
from .utils import version_table, version_class, option


class RelationshipBuilder(object):
    def __init__(self, versioning_manager, model, property_):
        self.manager = versioning_manager
        self.property = property_
        self.model = model

    def one_to_many_subquery(self, obj):
        primary_keys = []

        tx_column = option(obj, 'transaction_column_name')

        for column in self.remote_cls.__table__.c:
            if column.primary_key and column.name != tx_column:
                primary_keys.append(column)

        return getattr(self.remote_cls, tx_column).in_(
            sa.select(
                [sa.func.max(getattr(self.remote_cls, tx_column))]
            ).where(
                getattr(self.remote_cls, tx_column) <=
                getattr(obj, tx_column)
            ).group_by(
                *primary_keys
            ).correlate(self.local_cls)
        )

    def many_to_one_subquery(self, obj):
        tx_column = option(obj, 'transaction_column_name')
        reflector = ObjectExpressionReflector(obj)

        return getattr(self.remote_cls, tx_column).in_(
            sa.select(
                [sa.func.max(getattr(self.remote_cls, tx_column))]
            ).where(
                sa.and_(
                    getattr(self.remote_cls, tx_column) <=
                    getattr(obj, tx_column),
                    reflector(self.property.primaryjoin)
                )
            ).correlate(self.local_cls)
        )

    def query(self, obj):
        session = sa.orm.object_session(obj)
        return (
            session.query(self.remote_cls)
            .filter(
                self.criteria(obj)
            )
        )

    def process_query(self, query):
        """
        Process given SQLAlchemy Query object depending on the associated
        RelationshipProperty object.

        :param query: SQLAlchemy Query object
        """
        if self.property.lazy == 'dynamic':
            return query
        if self.property.uselist is False:
            return query.first()
        return query.all()

    def criteria(self, obj):
        direction = self.property.direction
        if direction.name == 'ONETOMANY':
            return self.one_to_many_criteria(obj)
        elif direction.name == 'MANYTOMANY':
            return self.many_to_many_criteria(obj)
        elif direction.name == 'MANYTOONE':
            return self.many_to_one_criteria(obj)

    def many_to_many_criteria(self, obj):
        tx_column = option(obj, 'transaction_column_name')
        condition = (
            getattr(self.remote_cls, tx_column) == sa.select(
                [sa.func.max(getattr(self.remote_cls, tx_column))]
            ).where(
                sa.and_(
                    getattr(self.remote_cls, tx_column) <=
                    getattr(obj, tx_column),
                )
            ).correlate(self.local_cls)
        )
        return sa.and_(
            self.remote_cls.id.in_(self.association_subquery(obj)),
            condition
        )

    def many_to_one_criteria(self, obj):
        reflector = ObjectExpressionReflector(obj)
        return sa.and_(
            reflector(self.property.primaryjoin),
            self.many_to_one_subquery(obj),
            self.remote_cls.operation_type != Operation.DELETE
        )

    def one_to_many_criteria(self, obj):
        reflector = ObjectExpressionReflector(obj)
        return sa.and_(
            reflector(self.property.primaryjoin),
            self.one_to_many_subquery(obj),
            self.remote_cls.operation_type != Operation.DELETE
        )

    @property
    def reflected_relationship(self):
        """
        Builds a reflected one-to-many, one-to-one and many-to-one
        relationship between two version classes.
        """
        @property
        def relationship(obj):
            query = self.query(obj)
            return self.process_query(query)
        return relationship

    def association_subquery(self, obj):
        """
        Returns association subquery for given SQLAlchemy declarative object.
        This query is used by many_to_many_criteria method.

        Example query:

        .. code-block:: sql

            SELECT article_tag_version.tag_id
            FROM article_tag_version
            WHERE
                article_tag_version.transaction_id IN (
                    SELECT max(article_tag_version.transaction_id) AS max_1
                    FROM article_tag_version
                    WHERE
                        article_tag_version.transaction_id <= ? AND
                        article_tag_version.article_id = ?
                    GROUP BY article_tag_version.tag_id
                ) AND
                article_tag_version.article_id = ? AND
                article_tag_version.operation_type != ?


        :param obj: SQLAlchemy declarative object
        """
        tx_column = option(obj, 'transaction_column_name')
        reflector = ObjectExpressionReflector(obj)
        subquery = (
            getattr(self.remote_table.c, tx_column).in_(
                sa.select(
                    [sa.func.max(getattr(self.remote_table.c, tx_column))],
                ).where(
                    sa.and_(
                        getattr(self.remote_table.c, tx_column) <=
                        getattr(obj, tx_column),
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
                    reflector(self.property.primaryjoin),
                    self.remote_table.c.operation_type != Operation.DELETE
                )
            )
        )

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

        if self.property.secondary is not None:
            self.build_association_version_tables()

            for column_pair in self.property.local_remote_pairs:
                if column_pair[0] in self.property.table.c.values():
                    self.remote_column = column_pair[1]
                    break

            self.remote_table = version_table(self.remote_column.table)
        setattr(
            self.local_cls,
            self.property.key,
            self.reflected_relationship
        )
