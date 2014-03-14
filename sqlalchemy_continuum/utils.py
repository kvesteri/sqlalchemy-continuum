from inspect import isclass
from collections import defaultdict
import sqlalchemy as sa
from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.exc import UnmappedInstanceError
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.util import AliasedClass
from sqlalchemy_utils.functions import naturally_equivalent


def get_versioning_manager(obj_or_class):
    """
    Return the associated SQLAlchemy-Continuum VersioningManager for given
    SQLAlchemy declarative model class or object.

    :param obj_or_class: SQLAlchemy declarative model object or class
    """
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


def get_bind(obj):
    if hasattr(obj, 'bind'):
        conn = obj.bind
    else:
        try:
            conn = object_session(obj).bind
        except UnmappedInstanceError:
            conn = obj

    if not isinstance(conn, sa.engine.base.Connection):
        raise TypeError(
            'This method accepts only Session, Connection and declarative '
            'model objects.'
        )
    return conn


def parent_class(version_cls):
    """
    Return the parent class for given version model class.

    ::

        parent_class(ArticleVersion)  # Article class


    :param model: SQLAlchemy declarative version model class

    .. seealso:: :func:`version_class`
    """
    return get_versioning_manager(version_cls).parent_class_map[version_cls]


def version_class(model):
    """
    Return the version class for given SQLAlchemy declarative model class.

    ::

        version_class(Article)  # ArticleVersion class


    :param model: SQLAlchemy declarative model class

    .. seealso:: :func:`parent_class`
    """
    return get_versioning_manager(model).version_class_map[model]


def version_table(table):
    """
    Return associated version table for given SQLAlchemy Table object.

    :param table: SQLAlchemy Table object
    """
    if table.metadata.schema:
        return table.metadata.tables[
            table.metadata.schema + '.' + table.name + '_version'
        ]
    else:
        return table.metadata.tables[
            table.name + '_version'
        ]


def versioned_objects(session):
    """
    Return all versioned objects in given session.

    :param session: SQLAlchemy session object

    .. seealso:: :func:`is_versioned`
    """
    for obj in session:
        if is_versioned(obj):
            yield obj


def is_versioned(obj_or_class):
    """
    Return whether or not given object is versioned.

    ::

        is_versioned(Article)  # True

        article = Article()

        is_versioned(article)  # True


    :param obj_or_class:
        SQLAlchemy declarative model object or SQLAlchemy declarative model
        class.

    .. seealso:: :func:`versioned_objects`
    """
    try:
        return (
            hasattr(obj_or_class, '__versioned__') and
            get_versioning_manager(obj_or_class).option(
                obj_or_class, 'versioning'
            )
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
    When making structural changes to version tables (for example dropping
    columns) there are sometimes situations where some old version records
    become futile.

    Vacuum deletes all futile version rows which had no changes compared to
    previous version.


    ::


        from sqlalchemy_continuum import vacuum


        vacuum(session, User)  # vacuums user version


    :param session: SQLAlchemy session object
    :param model: SQLAlchemy declarative model class
    """
    version_cls = version_class(model)
    versions = defaultdict(list)

    query = (
        session.query(version_cls)
        .order_by(option(version_cls, 'transaction_column_name'))
    )

    for version in query:
        if versions[version.id]:
            prev_version = versions[version.id][-1]
            if naturally_equivalent(prev_version, version):
                session.delete(version)
        else:
            versions[version.id].append(version)


def is_internal_column(model, column_name):
    """
    Return whether or not given column of given SQLAlchemy declarative classs
    is considered an internal column (a column whose purpose is mainly
    for SA-Continuum's internal use).

    :param version_obj: SQLAlchemy declarative class
    :param column_name: Name of the column
    """
    return column_name in (
        option(model, 'transaction_column_name'),
        option(model, 'end_transaction_column_name'),
        option(model, 'operation_type_column_name')
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

    ::

        article = Article()

        is_modified(article)  # False

        article.name = 'Something'

        is_modified(article)  # True


    :param obj: SQLAlchemy declarative model object

    .. seealso:: :func:`is_modified_or_deleted`
    .. seealso:: :func:`is_session_modified`
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


def is_session_modified(session):
    """
    Return whether or not any of the versioned objects in given session have
    been either modified or deleted.

    :param session: SQLAlchemy session object

    .. seealso:: :func:`is_versioned`
    .. seealso:: :func:`versioned_objects`
    """
    return any(
        is_modified_or_deleted(obj) for obj in versioned_objects(session)
    )


def changeset(obj):
    """
    Return a humanized changeset for given SQLAlchemy declarative object. With
    this function you can easily check the changeset of given object in current
    transaction.

    ::


        from sqlalchemy_continuum import changeset


        article = Article(name=u'Some article')
        changeset(article)
        # {'name': [u'Some article', None]}

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
