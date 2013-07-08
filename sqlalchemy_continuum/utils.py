import sqlalchemy as sa
import itertools


def declarative_base(model):
    """
    Returns the declarative base for given model class.

    :param model: SQLAlchemy declarative model
    """
    for parent in model.__bases__:
        try:
            parent.metadata
            return declarative_base(parent)
        except AttributeError:
            pass
    return model


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


def is_auto_assigned_date_column(column):
    """
    Returns whether or not given SQLAlchemy Column object's is auto assigned
    DateTime or Date.

    :param column: SQLAlchemy Column object
    """
    return (
        (
            isinstance(column.type, sa.DateTime) or
            isinstance(column.type, sa.Date)
        )
        and
        column.default or column.server_default or
        column.onupdate or column.server_onupdate
    )


def identity(obj):
    """
    Return the identity of given sqlalchemy declarative model instance as a
    tuple. This differs from obj._sa_instance_state.identity in a way that it
    always returns the identity even if object is still in transient state (
    new object that is not yet persisted into database).

    :param obj: SQLAlchemy declarative model object
    """
    id_ = []
    for attr in obj._sa_class_manager.values():
        prop = attr.property
        if isinstance(prop, sa.orm.ColumnProperty):
            column = prop.columns[0]
            if column.primary_key:
                id_.append(getattr(obj, column.name))
    return tuple(id_)
