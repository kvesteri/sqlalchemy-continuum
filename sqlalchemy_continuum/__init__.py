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

    uow = manager.uow

    sa.event.listen(
        mapper, 'before_delete', uow.track_deletes
    )
    sa.event.listen(
        mapper, 'before_update', uow.track_updates
    )
    sa.event.listen(
        mapper, 'before_insert', uow.track_inserts
    )

    sa.event.listen(
        session, 'after_flush', uow.create_version_objects
    )
    sa.event.listen(
        session, 'after_flush', uow.create_transaction_changes_entries
    )

    sa.event.listen(
        session, 'before_commit', uow.create_transaction_log_entry
    )
    sa.event.listen(
        session, 'before_commit', uow.before_commit
    )

    sa.event.listen(
        sa.engine.Engine,
        'before_cursor_execute',
        uow.version_association_table_records
    )

    sa.event.listen(
        session, 'after_commit', uow.clear_transaction
    )
    sa.event.listen(
        session, 'after_rollback', uow.clear_transaction
    )
