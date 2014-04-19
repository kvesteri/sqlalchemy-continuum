import sqlalchemy as sa
from .manager import VersioningManager
from .operation import Operation
from .unit_of_work import UnitOfWork
from .utils import (
    changeset,
    get_versioning_manager,
    parent_class,
    transaction_class,
    vacuum,
    version_class,
)


__version__ = '1.0-b3'


versioning_manager = VersioningManager()


def make_versioned(
    mapper=sa.orm.mapper,
    session=sa.orm.session.Session,
    manager=versioning_manager,
    plugins=None,
    options=None
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
        SQLAlchemy-Continuum versioning manager.
    :param plugins:
        Plugins to pass for versioning manager.
    :param options:
        A dictionary of VersioningManager options.
    """
    if plugins is not None:
        manager.plugins = plugins

    if options is not None:
        manager.options.update(options)

    manager.apply_class_configuration_listeners(mapper)
    manager.track_operations(mapper)
    manager.track_session(session)

    sa.event.listen(
        sa.engine.Engine,
        'before_cursor_execute',
        manager.track_association_operations
    )


def remove_versioning(
    mapper=sa.orm.mapper,
    session=sa.orm.session.Session,
    manager=versioning_manager
):
    """
    Remove the versioning from given mapper / session and manager.

    :param mapper:
        SQLAlchemy mapper to remove the versioning from.
    :param session:
        SQLAlchemy session to remove the versioning from. By default this is
        sa.orm.session.Session meaning it applies to all sessions.
    :param manager:
        SQLAlchemy-Continuum versioning manager.
    """
    manager.reset()
    manager.remove_class_configuration_listeners(mapper)
    manager.remove_operations_tracking(mapper)
    manager.remove_session_tracking(session)
    sa.event.remove(
        sa.engine.Engine,
        'before_cursor_execute',
        manager.track_association_operations
    )
