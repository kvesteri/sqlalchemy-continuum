import sqlalchemy as sa
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

    object = generic_relationship(object_type, object_id)

    # This is used to discriminate between the linked tables.
    target_type = sa.Column(sa.Unicode(255))

    # This is used to point to the primary key of the linked row.
    target_id = sa.Column(sa.Integer)

    target = generic_relationship(target_type, target_id)

    @hybrid_property
    def actor(self):
        self.transaction.user
