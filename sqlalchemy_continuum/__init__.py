import sqlalchemy as sa
from .manager import VersioningManager

__all__ = (
    VersioningManager
)


versioning_manager = VersioningManager()


class Operation(object):
    INSERT = 0
    UPDATE = 1
    DELETE = 2


class Versioned(object):
    __versioned__ = {}

    revision = sa.Column(sa.Integer)


def make_versioned(
    mapper=sa.orm.mapper,
    session=sa.orm.session.Session,
    manager=versioning_manager
):
    sa.event.listen(
        mapper, 'instrument_class', manager.instrument_versioned_classes
    )
    sa.event.listen(
        mapper, 'after_configured', manager.configure_versioned_classes
    )
    sa.event.listen(
        session, 'before_flush', manager.assign_revisions
    )
    sa.event.listen(
        session, 'after_flush', manager.create_version_objects
    )
    sa.event.listen(
        session, 'before_commit', manager.create_transaction_log_entry
    )
    sa.event.listen(
        session, 'before_commit', manager.create_transaction_changes_entries
    )

    # after_insert(mapper, connection, target)
    sa.event.listen(
        sa.engine.Engine,
        'before_cursor_execute',
        manager.version_association_table_records
    )
