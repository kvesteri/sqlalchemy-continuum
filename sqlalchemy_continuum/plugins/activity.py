import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import JSONType, generic_relationship

from .base import ModelFactory


class ActivityBase(object):
    id = sa.Column(sa.BigInteger, primary_key=True, autoincrement=True)

    transaction_id = sa.Column(
        sa.BigInteger,
        primary_key=True,
        nullable=False
    )

    verb = sa.Column(sa.Unicode(255))

    data = sa.Column(JSONType)

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
            self.declarative_base,
            ActivityBase
        ):
            __tablename__ = 'activity'
            manager = self

            object_type = sa.Column(sa.String(255))

            object_id = sa.Column(sa.Integer)

            target_type = sa.Column(sa.String(255))

            target_id = sa.Column(sa.Integer)

            object = generic_relationship(
                object_type, object_id
            )

            target = generic_relationship(
                target_type, target_id
            )

        return Activity
