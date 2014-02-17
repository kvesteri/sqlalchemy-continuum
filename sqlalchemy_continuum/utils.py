from inspect import isclass
from collections import defaultdict
import itertools
import sqlalchemy as sa
from sqlalchemy.orm.attributes import get_history
from sqlalchemy_utils.functions import naturally_equivalent


def tx_cls(obj):
    pass


def versioning_manager(obj):
    cls = obj if isclass(obj) else obj.__class__
    return cls.__versioning_manager__


def tx_meta_cls(obj):
    pass


def tx_changes_cls(obj):
    pass


def tx_column_name(obj):
    return versioning_manager(obj).option(
        obj.__parent_class__,
        'transaction_column_name'
    )


def end_tx_column_name(obj):
    return versioning_manager(obj).option(
        obj.__parent_class__,
        'end_transaction_column_name'
    )


def end_tx_attr(obj):
    return getattr(
        obj.__class__,
        versioning_manager(obj).option(
            obj.__parent_class__,
            'end_transaction_column_name'
        )
    )


def history_table(table):
    """
    Return associated history table for given SQLAlchemy Table object.

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
    Return all versioned objects in given session.

    :param session: SQLAlchemy session object
    """
    iterator = itertools.chain(session.new, session.dirty, session.deleted)

    return [
        obj for obj in iterator
        if is_versioned(obj)
    ]


def is_versioned(obj):
    """
    Return whether or not given object is versioned.

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
    Return all versioned column properties for given versioned SQLAlchemy
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


def is_internal_column(history_obj, column_name):
    """
    Return whether or not given column of given SQLAlchemy declarative history
    object is considered an internal column (a column whose purpose is mainly
    for SA-Continuum's internal use).

    :param history_obj: SQLAlchemy declarative history object
    :param column_name: Name of the column
    """
    manager = versioning_manager(history_obj)
    parent_cls = history_obj.__parent_class__

    return column_name in (
        manager.option(parent_cls, 'transaction_column_name'),
        manager.option(parent_cls, 'end_transaction_column_name'),
        manager.option(parent_cls, 'operation_type_column_name')
    ) or column_name.endswith(
        manager.option(parent_cls, 'modified_flag_suffix')
    )


def is_modified_or_deleted(obj):
    """
    Return whether or not some of the versioned properties of given SQLAlchemy
    declarative object have been modified or if the object has been deleted.

    :param obj: SQLAlchemy declarative model object
    """
    session = sa.orm.object_session(obj)
    return is_modified(obj) or obj in session.deleted


def is_modified(obj):
    """
    Return whether or not the versioned properties of given object have been
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
    Return a humanized changeset for given SQLAlchemy declarative object.

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
