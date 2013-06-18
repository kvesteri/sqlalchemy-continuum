import sqlalchemy as sa
from .versioned import Versioned
from .manager import VersioningManager

__all__ = (
    Versioned,
    VersioningManager
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


def make_versioned(mapper, manager_class=VersioningManager):
    manager = manager_class()
    sa.event.listen(
        mapper, 'instrument_class', manager.instrument_versioned_classes
    )
    sa.event.listen(
        mapper, 'after_configured', manager.configure_versioned_classes
    )
