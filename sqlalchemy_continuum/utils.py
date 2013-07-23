import itertools
import sqlalchemy as sa
from sqlalchemy.orm.attributes import get_history


def versioned_objects(session):
    """
    Returns all versioned objects in given session.

    :param session: SQLAlchemy session object
    """
    iterator = itertools.chain(session.new, session.dirty, session.deleted)

    return [
        obj for obj in iterator
        if is_versioned(obj)
    ]


def is_versioned(obj):
    """
    Returns whether or not given object is versioned.

    :param obj: SQLAlchemy declarative model object.
    """
    return (
        hasattr(obj, '__versioned__') and
        (
            (
                'versioning' in obj.__versioned__ and
                obj.__versioned__['versioning']
            ) or
            'versioning' not in obj.__versioned__
        )
    )


def changeset(obj):
    """
    Returns a humanized changeset for given SQLAlchemy declarative object.

    :param obj: SQLAlchemy declarative
    """
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
