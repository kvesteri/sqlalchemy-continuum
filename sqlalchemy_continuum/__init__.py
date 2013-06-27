import sqlalchemy as sa
from .manager import VersioningManager
from .operation import Operation


__all__ = (
    Operation,
    VersioningManager
)


versioning_manager = VersioningManager()


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
        mapper, 'before_delete', manager.track_deletes
    )
    sa.event.listen(
        mapper, 'before_update', manager.track_updates
    )
    sa.event.listen(
        mapper, 'before_insert', manager.track_inserts
    )

    sa.event.listen(
        session, 'after_flush', manager.create_version_objects
    )
    sa.event.listen(
        session, 'after_flush', manager.create_transaction_changes_entries
    )

    sa.event.listen(
        session, 'before_commit', manager.create_transaction_log_entry
    )
    sa.event.listen(
        session, 'before_commit', manager.before_commit
    )

    sa.event.listen(
        sa.engine.Engine,
        'before_cursor_execute',
        manager.version_association_table_records
    )

    sa.event.listen(
        session, 'after_commit', manager.clear_transaction
    )
    sa.event.listen(
        session, 'after_rollback', manager.clear_transaction
    )
