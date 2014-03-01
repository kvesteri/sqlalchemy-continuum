import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import generic_relationship, JSONType


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
