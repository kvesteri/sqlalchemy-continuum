import itertools
import sqlalchemy as sa
from sqlalchemy.orm.attributes import get_history


def history_table(table):
    """
    Returns associated history table for given SQLAlchemy Table object.

    :param table: SQLAlchemy Table object
    """
    if table.metadata.schema:
        return table.metadata.tables[
            table.metadata.schema + '.' + table.name + '_history'
        ]
    else:
        return table.metadata.tables[
            table.name + '_history'
        ]


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


def has_changes(obj, attr):
    """
    Simple shortcut function for checking if given attribute of given
    declarative model object has changed during the transaction.

    :param obj: SQLAlchemy declarative model object
    :param attr: Name of the attribute
    """
    return (
        sa.inspect(obj)
        .attrs
        .get(attr)
        .history
        .has_changes()
    )


def is_modified(obj):
    """
    Returns whether or not the versioned properties of given object have been
    modified.

    :param obj: SQLAlchemy declarative model object.
    """
    manager = obj.__versioned__['manager']

    for prop in obj.__mapper__.iterate_properties:
        if (
            isinstance(prop, sa.orm.ColumnProperty) and
            not manager.is_excluded_column(obj, prop.columns[0])
        ):
            attr = getattr(obj._sa_instance_state.attrs, prop.key)
            if attr.history.has_changes():
                return True
    return False


def changeset(obj):
    """
    Returns a humanized changeset for given SQLAlchemy declarative object.

    :param obj: SQLAlchemy declarative model object.
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
