import sqlalchemy as sa
from .manager import VersioningManager
from .operation import Operation
from sqlalchemy.orm.attributes import get_history


__version__ = '0.7.7'


__all__ = (
    Operation,
    VersioningManager
)


versioning_manager = VersioningManager()


class Versioned(object):
    __versioned__ = {}


def changeset(obj):
    data = {}
    session = sa.orm.object_session(obj)
    if session and obj in session.deleted:
        for attr in obj.__mapper__.class_manager.values():
            if isinstance(attr.property, sa.orm.ColumnProperty):
                if not attr.property.columns[0].primary_key:
                    value = getattr(obj, attr.key)
                    if value is not None:
                        data[attr.key] = [None, getattr(obj, attr.key)]
    else:
        for attr in obj.__mapper__.class_manager.values():
            history = get_history(obj, attr.key)
            if history.has_changes():
                old_value = history.deleted[0] if history.deleted else None
                new_value = history.added[0] if history.added else None

                if new_value:
                    data[attr.key] = [new_value, old_value]
    return data


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
