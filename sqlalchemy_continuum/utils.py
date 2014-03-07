from inspect import isclass
from collections import defaultdict
import sqlalchemy as sa
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.util import AliasedClass
from sqlalchemy_utils.functions import naturally_equivalent


def get_versioning_manager(obj_or_class):
    if isinstance(obj_or_class, AliasedClass):
        obj_or_class = sa.inspect(obj_or_class).mapper.class_
    cls = obj_or_class if isclass(obj_or_class) else obj_or_class.__class__
    return cls.__versioning_manager__


def option(obj_or_class, option_name):
    if isinstance(obj_or_class, AliasedClass):
        obj_or_class = sa.inspect(obj_or_class).mapper.class_
    cls = obj_or_class if isclass(obj_or_class) else obj_or_class.__class__
    if not hasattr(cls, '__versioned__'):
        cls = parent_class(cls)
    return get_versioning_manager(cls).option(
        cls, option_name
    )


def tx_column_name(obj):
    return option(obj, 'transaction_column_name')


def end_tx_column_name(obj):
    return option(obj, 'end_transaction_column_name')


def end_tx_attr(obj):
    return getattr(
        obj.__class__,
        end_tx_column_name(obj)
    )


def parent_class(history_cls):
    return get_versioning_manager(history_cls).history_class_map[history_cls]


def history_class(model):
    return get_versioning_manager(model).history_class_map[model]


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
    for obj in session:
        if is_versioned(obj):
            yield obj


def is_versioned(mixed):
    """
    Return whether or not given object is versioned.

    :param mixed:
        SQLAlchemy declarative model object or SQLAlchemy declarative model.
    """
    try:
        return (
            hasattr(mixed, '__versioned__') and
            get_versioning_manager(mixed).option(mixed, 'versioning')
        )
    except (AttributeError, KeyError):
        return False


def versioned_column_properties(obj_or_class):
    """
    Return all versioned column properties for given versioned SQLAlchemy
    declarative model object.

    :param obj: SQLAlchemy declarative model object
    """
    manager = get_versioning_manager(obj_or_class)

    cls = obj_or_class if isclass(obj_or_class) else obj_or_class.__class__

    for prop in sa.inspect(cls).attrs.values():
        if not isinstance(prop, ColumnProperty):
            continue
        if not manager.is_excluded_column(obj_or_class, prop.columns[0]):
            yield prop


def versioned_relationships(obj):
    """
    Return all versioned relationships for given versioned SQLAlchemy
    declarative model object.

    :param obj: SQLAlchemy declarative model object
    """
    for prop in sa.inspect(obj.__class__).relationships:
        if is_versioned(prop.mapper.class_):
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
    history_cls = history_class(model)
    versions = defaultdict(list)

    query = (
        session.query(history_cls)
        .order_by(option(history_cls, 'transaction_column_name'))
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
    manager = get_versioning_manager(history_obj)
    parent_cls = parent_class(history_obj.__class__)

    return column_name in (
        manager.option(parent_cls, 'transaction_column_name'),
        manager.option(parent_cls, 'end_transaction_column_name'),
        manager.option(parent_cls, 'operation_type_column_name')
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
    column_names = sa.inspect(obj.__class__).columns.keys()
    versioned_column_keys = [
        prop.key for prop in versioned_column_properties(obj)
    ]
    versioned_relationship_keys = [
        prop.key for prop in versioned_relationships(obj)
    ]
    for key, attr in sa.inspect(obj).attrs.items():
        if key in column_names:
            if key not in versioned_column_keys:
                continue
            if attr.history.has_changes():
                return True
        if key in versioned_relationship_keys:
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
        for column in sa.inspect(obj.__class__).columns.values():
            if not column.primary_key:
                value = getattr(obj, column.key)
                if value is not None:
                    data[column.key] = [None, getattr(obj, column.key)]
    else:
        for prop in obj.__mapper__.iterate_properties:
            history = get_history(obj, prop.key)
            if history.has_changes():
                old_value = history.deleted[0] if history.deleted else None
                new_value = history.added[0] if history.added else None

                if new_value:
                    data[prop.key] = [new_value, old_value]
    return data
