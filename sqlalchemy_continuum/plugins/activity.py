import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import JSONType, generic_relationship

from .base import ModelFactory, Plugin


class ActivityBase(object):
    id = sa.Column(sa.BigInteger, primary_key=True, autoincrement=True)

    verb = sa.Column(sa.Unicode(255))

    @hybrid_property
    def actor(self):
        self.transaction.user


class ActivityFactory(ModelFactory):
    model_name = 'Activity'

    def create_class(self):
        """
        Create Activity class.
        """
        class Activity(
            self.manager.declarative_base,
            ActivityBase
        ):
            __tablename__ = 'activity'
            manager = self

            transaction_id = sa.Column(
                sa.BigInteger,
                primary_key=True,
                nullable=False
            )

            data = sa.Column(JSONType)

            object_type = sa.Column(sa.String(255))

            object_id = sa.Column(sa.Integer)

            target_type = sa.Column(sa.String(255))

            target_id = sa.Column(sa.Integer)

            object = generic_relationship(
                object_type, object_id
            )

            @hybrid_property
            def object_version_type(self):
                return self.object_type + 'History'

            @object_version_type.expression
            def object_version_type(cls):
                return sa.func.concat(cls.object_type, 'History')

            object_version = generic_relationship(
                object_version_type, (object_id, transaction_id)
            )

            target = generic_relationship(
                target_type, target_id
            )

            @hybrid_property
            def target_version_type(self):
                return self.target_type + 'History'

            @target_version_type.expression
            def target_version_type(cls):
                return sa.func.concat(cls.target_type, 'History')

            target_version = generic_relationship(
                target_version_type, (target_id, transaction_id)
            )

        Activity.transaction = sa.orm.relationship(
            self.manager.transaction_log_cls,
            backref=sa.orm.backref(
                'changes',
            ),
            primaryjoin=(
                '%s.id == Activity.transaction_id' %
                self.manager.transaction_log_cls.__name__
            ),
            foreign_keys=[Activity.transaction_id]
        )
        return Activity


class ActivityPlugin(Plugin):
    def after_build_tx_class(self):
        self.model_class = ActivityFactory(self.manager)()
        self.manager.activity_cls = self.model_class

    def before_flush(self, uow, session):
        for obj in session:
            if isinstance(obj, self.model_class):
                obj.transaction = uow.current_transaction

    def after_history_class_built(self, parent_cls, history_cls):
        pass
