import sqlalchemy as sa
from .manager import VersioningManager
from .operation import Operation
from .utils import changeset


__version__ = '0.10.0'


__all__ = (
    changeset,
    Operation,
    VersioningManager
)


versioning_manager = VersioningManager()


def make_versioned(
    mapper=sa.orm.mapper,
    session=sa.orm.session.Session,
    manager=versioning_manager
):
    """
    This is the public API function of SQLAlchemy-Continuum for making certain
    mappers and sessions versioned. By default this applies to all mappers and
    all sessions.

    :param mapper:
        SQLAlchemy mapper to apply the versioning to.
    :param session:
        SQLAlchemy session to apply the versioning to. By default this is
        sa.orm.session.Session meaning it applies to all Session subclasses.
    :param manager:
        The versioning manager. Override this if you want to use one of
        SQLAlchemy-Continuum's extensions (eg. Flask extension)
    """
    manager.apply_class_configuration_listeners(mapper)
    uow = manager.uow
    uow.track_operations(mapper)
    uow.track_session(session)

    sa.event.listen(
        sa.engine.Engine,
        'before_cursor_execute',
        uow.track_association_operations
    )
