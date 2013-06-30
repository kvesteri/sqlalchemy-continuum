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
    uow.track_operations(mapper)
    uow.track_session(session)

    sa.event.listen(
        sa.engine.Engine,
        'before_cursor_execute',
        uow.version_association_table_records
    )
