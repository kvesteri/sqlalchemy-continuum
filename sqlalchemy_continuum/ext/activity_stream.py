import sqlalchemy as sa
from sqlalchemy_utils import generic_relationship, JSONType


class Activity(object):
    @declared_attr
    def actor_id(self):
        return sa.Column(
            sa.Integer,
            sa.ForeignKey('user.id'),
            index=True
        )

    @declared_attr
    def actor(self):
        return sa.orm.relationship('User')

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
