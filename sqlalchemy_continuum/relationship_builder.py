import sqlalchemy as sa
from .builder import VersionedBuilder
from .expression_reflector import ObjectExpressionReflector


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
            reflector = ObjectExpressionReflector(obj)
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
