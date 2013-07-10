import sqlalchemy as sa
from .builder import VersionedBuilder
from .table_builder import VersionedTableBuilder
from .expression_reflector import ObjectExpressionReflector
from .operation import Operation


class RelationshipBuilder(VersionedBuilder):
    def reflected_relationship_factory(
        self,
        local_cls,
        remote_cls,
        primary_join
    ):
        @property
        def relationship(obj):
            session = sa.orm.object_session(obj)
            primary_keys = []
            for column in remote_cls.__table__.c:
                if column.primary_key and column.name != 'transaction_id':
                    primary_keys.append(column)

            condition = remote_cls.transaction_id.in_(
                sa.select(
                    [sa.func.max(remote_cls.transaction_id)]
                ).where(
                    remote_cls.transaction_id <= obj.transaction_id
                ).group_by(
                    *primary_keys
                ).correlate(local_cls)
            )
            reflector = ObjectExpressionReflector(obj)
            return (
                session.query(remote_cls)
                .filter(
                    sa.and_(
                        reflector(primary_join),
                        condition,
                        remote_cls.operation_type != Operation.DELETE
                    )
                )
            )
        return relationship

    def reflected_association_factory(
        self,
        local_cls,
        remote_cls,
        property_
    ):
        primary_join = property_.primaryjoin
        table = None
        column = None
        for column_pair in property_.local_remote_pairs:
            if column_pair[0] in property_.table.c.values():
                column = column_pair[1]
                break

        table = column.table.metadata.tables[column.table.name + '_history']

        @property
        def relationship(obj):
            session = sa.orm.object_session(obj)
            reflector = ObjectExpressionReflector(obj)
            condition = (
                table.c.transaction_id.in_(
                    sa.select(
                        [sa.func.max(table.c.transaction_id)],
                    ).where(
                        sa.and_(
                            table.c.transaction_id <= obj.transaction_id,
                            reflector(primary_join)
                        )
                    ).group_by(
                        table.c[column.name]
                    ).correlate(local_cls)
                )
            )

            sql = (
                sa.select(
                    [table.c[column.name]]
                ).where(
                    sa.and_(
                        condition,
                        table.c.operation_type != Operation.DELETE
                    )
                )
            )
            condition = (
                remote_cls.transaction_id == sa.select(
                    [sa.func.max(remote_cls.transaction_id)]
                ).where(
                    remote_cls.transaction_id <= obj.transaction_id
                ).correlate(local_cls)
            )
            return (
                session.query(remote_cls)
                .filter(
                    sa.and_(
                        remote_cls.id.in_(
                            sql
                        ),
                        condition
                    )
                )
            )
        return relationship

    def build_association_version_tables(self, property_):
        """
        Builds many-to-many association history table for given property.
        Association history tables are used for tracking change history of
        many-to-many associations.

        :param property_: RelationshipProperty instance
        """
        column = list(property_.remote_side)[0]

        self.manager.association_tables.add(column.table)
        builder = VersionedTableBuilder(
            self.manager,
            column.table,
            remove_primary_keys=True
        )
        if builder.table_name not in column.table.metadata.tables:
            version_table = builder.build_table()

            self.manager.association_history_tables.add(
                version_table
            )

    def build_reflected_relationship(self, property_):
        """
        Builds reflected relationship between history classes based on given
        parent object's RelationshipProperty.

        :param property_: RelationshipProperty instance
        """
        local_cls = self.model.__versioned__['class']
        try:
            remote_cls = property_.mapper.class_.__versioned__['class']
        except (AttributeError, KeyError):
            return
        primary_join = property_.primaryjoin

        if property_.secondary is not None:
            setattr(
                local_cls,
                property_.key,
                self.reflected_association_factory(
                    local_cls,
                    remote_cls,
                    property_,
                )
            )
        else:
            setattr(
                local_cls,
                property_.key,
                self.reflected_relationship_factory(
                    local_cls, remote_cls, primary_join
                )
            )

    def build_reflected_relationships(self):
        """
        Build reflected relationships for history model based on defined
        relationships of parent model.
        """
        for attr in self.attrs:
            if attr.key == 'versions':
                continue
            property_ = attr.property
            if isinstance(property_, sa.orm.RelationshipProperty):
                if property_.remote_side and property_.secondary is not None:
                    self.build_association_version_tables(property_)

                self.build_reflected_relationship(property_)
