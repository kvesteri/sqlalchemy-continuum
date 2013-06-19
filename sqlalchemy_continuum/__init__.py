import sqlalchemy as sa
from .manager import VersioningManager

__all__ = (
    VersioningManager
)


versioning_manager = VersioningManager()


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
        session, 'before_commit', manager.create_transaction_log_entries
    )
    sa.event.listen(
        session, 'before_commit', manager.create_transaction_changes_entries
    )
