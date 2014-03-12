import sqlalchemy as sa
from .manager import VersioningManager
from .operation import Operation
from .unit_of_work import UnitOfWork
from .utils import (
    changeset,
    get_versioning_manager,
    version_class,
    parent_class,
    vacuum,
)


__version__ = '1.0-dev'


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
        The versioning manager. Override this if you want to use one of
        SQLAlchemy-Continuum's extensions (eg. Flask extension)
    :param plugins:
        Plugins to pass for versioning manager.
    :param options:
        A dictionary of VersioningManager options.
    """
    if plugins is not None:
        manager.plugins = plugins
    manager.apply_class_configuration_listeners(mapper)
    manager.track_operations(mapper)
    manager.track_session(session)

    if options is not None:
        manager.options.update(options)

    sa.event.listen(
        sa.engine.Engine,
        'before_cursor_execute',
        manager.track_association_operations
    )
