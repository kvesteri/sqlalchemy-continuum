from collections import defaultdict
import itertools
import sqlalchemy as sa
from sqlalchemy.orm.attributes import get_history
from sqlalchemy_utils.functions import naturally_equivalent


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


def versioned_column_properties(obj):
    """
    Returns all versioned column properties for given versioned SQLAlchemy
    declarative model object.

    :param obj: SQLAlchemy declarative model object
    """
    manager = obj.__versioned__['manager']

    for prop in obj.__mapper__.iterate_properties:
        if (
            isinstance(prop, sa.orm.ColumnProperty) and
            not manager.is_excluded_column(obj, prop.columns[0])
        ):
            yield prop


def vacuum(session, model):
    """
    When making structural changes to history tables (for example dropping
    columns) there are sometimes situations where some old history records
    become futile.

    Vacuum deletes all futile history rows which had no changes compared to
    previous version.


    ::


        from sqlalchemy_continuum import vacuum


        vacuum(session, User)  # vacuums user history


    :param session: SQLAlchemy session object
    :param model: SQLAlchemy declarative model class
    """
    history_class = model.__versioned__['class']
    manager = model.__versioned__['manager']
    versions = defaultdict(list)

    query = (
        session.query(history_class)
        .order_by(manager.option(history_class, 'transaction_column_name'))
    )

    for version in query:
        if versions[version.id]:
            prev_version = versions[version.id][-1]
            if naturally_equivalent(prev_version, version):
                session.delete(version)
        else:
            versions[version.id].append(version)


def is_modified(obj):
    """
    Returns whether or not the versioned properties of given object have been
    modified.

    :param obj: SQLAlchemy declarative model object
    """
    for prop in versioned_column_properties(obj):
        attr = getattr(sa.inspect(obj).attrs, prop.key)
        if attr.history.has_changes():
            return True
    return False


def changeset(obj):
    """
    Returns a humanized changeset for given SQLAlchemy declarative object.

    :param obj: SQLAlchemy declarative model object
    """
    data = {}
    session = sa.orm.object_session(obj)
    if session and obj in session.deleted:
        for prop in obj.__mapper__.iterate_properties:
            if isinstance(prop, sa.orm.ColumnProperty):
                if not prop.columns[0].primary_key:
                    value = getattr(obj, prop.key)
                    if value is not None:
                        data[prop.key] = [None, getattr(obj, prop.key)]
    else:
        for prop in obj.__mapper__.iterate_properties:
            history = get_history(obj, prop.key)
            if history.has_changes():
                old_value = history.deleted[0] if history.deleted else None
                new_value = history.added[0] if history.added else None

                if new_value:
                    data[prop.key] = [new_value, old_value]
    return data
