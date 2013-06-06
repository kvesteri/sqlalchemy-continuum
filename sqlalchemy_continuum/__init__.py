import sqlalchemy as sa
from .versioned import Versioned
from .listener import configure_versioned

__all__ = (
    Versioned,
    configure_versioned
)


def versioned_objects(iterator):
    return [obj for obj in iterator if hasattr(obj, '__versioned__')]


def versioned_session(session):
    @sa.event.listens_for(session, 'before_commit')
    def before_commit(session):
        session.execute(
            '''INSERT INTO transaction_log (id, issued_at)
            VALUES (txid_current(), NOW())'''
        )
