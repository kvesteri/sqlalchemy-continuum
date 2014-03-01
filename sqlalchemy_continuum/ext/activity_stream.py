import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import generic_relationship, JSONType


class ActivityBase(object):
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    transaction_id = sa.Column(
        sa.BigInteger,
        primary_key=True
    )

    verb = sa.Column(sa.Unicode(255))

    data = sa.Column(JSONType)

    # This is used to discriminate between the linked tables.
    object_type = sa.Column(sa.Unicode(255))

    # This is used to point to the primary key of the linked row.
    object_id = sa.Column(sa.Integer)

    # This is used to discriminate between the linked tables.
    target_type = sa.Column(sa.Unicode(255))

    # This is used to point to the primary key of the linked row.
    target_id = sa.Column(sa.Integer)

    @declared_attr
    def object(cls):
        return generic_relationship(cls.object_type, cls.object_id)

    @declared_attr
    def target(cls):
        return generic_relationship(cls.target_type, cls.target_id)

    @hybrid_property
    def actor(self):
        self.transaction.user
