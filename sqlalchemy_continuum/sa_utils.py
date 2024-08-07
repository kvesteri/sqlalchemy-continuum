from inspect import isclass

import sqlalchemy as sa
from sqlalchemy.orm import ColumnProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute


def _get_columns(mixed):
    """
    Return a collection of all Column objects for given SQLAlchemy
    object.

    The type of the collection depends on the type of the object to return the
    columns from.

    ::

        get_columns(User)

        get_columns(User())

        get_columns(User.__table__)

        get_columns(User.__mapper__)

        get_columns(sa.orm.aliased(User))

        get_columns(sa.orm.alised(User.__table__))


    :param mixed:
        SA Table object, SA Mapper, SA declarative class, SA declarative class
        instance or an alias of any of these objects
    """
    if isinstance(mixed, sa.sql.selectable.Selectable):
        try:
            return mixed.selected_columns
        except AttributeError:  # SQLAlchemy <1.4
            return mixed.c
    if isinstance(mixed, sa.orm.util.AliasedClass):
        return sa.inspect(mixed).mapper.columns
    if isinstance(mixed, sa.orm.Mapper):
        return mixed.columns
    if isinstance(mixed, InstrumentedAttribute):
        return mixed.property.columns
    if isinstance(mixed, ColumnProperty):
        return mixed.columns
    if isinstance(mixed, sa.Column):
        return [mixed]
    if not isclass(mixed):
        mixed = mixed.__class__
    return sa.inspect(mixed).columns


def get_column_key(model, column):
    """
    Return the key for given column in given model.

    :param model: SQLAlchemy declarative model object

    ::

        class User(Base):
            __tablename__ = 'user'
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column('_name', sa.String)


        get_column_key(User, User.__table__.c._name)  # 'name'

    .. versionadded: 0.26.5

    .. versionchanged: 0.27.11
        Throws UnmappedColumnError instead of ValueError when no property was
        found for given column. This is consistent with how SQLAlchemy works.
    """
    mapper = sa.inspect(model)
    try:
        return mapper.get_property_by_column(column).key
    except sa.orm.exc.UnmappedColumnError:
        for key, c in mapper.columns.items():
            if c.name == column.name and c.table is column.table:
                return key
    raise sa.orm.exc.UnmappedColumnError(
        'No column %s is configured on mapper %s...' %
        (column, mapper)
    )


def get_declarative_base(model):
    """
    Returns the declarative base for given model class.

    :param model: SQLAlchemy declarative model
    """
    for parent in model.__bases__:
        try:
            parent.metadata
            return get_declarative_base(parent)
        except AttributeError:
            pass
    return model


def get_primary_key_columns(mixed):
    """
    Return all primary key names for given Table object,
    declarative class or declarative class instance.

    :param mixed:
        SA Table object, SA declarative class or SA declarative class instance

    ::

        get_primary_key_columns(User)

        get_primary_key_columns(User())

        get_primary_key_columns(User.__table__)

        get_primary_key_columns(User.__mapper__)

        get_primary_key_columns(sa.orm.aliased(User))

        get_primary_key_columns(sa.orm.aliased(User.__table__))
    """
    return [
        key  for key, column in _get_columns(mixed).items()
        if column.primary_key
    ]


def has_changes(obj, attrs=None, exclude=None):
    """
    Simple shortcut function for checking if given attributes of given
    declarative model object have changed during the session. Without
    parameters this checks if given object has any modificiations. Additionally
    exclude parameter can be given to check if given object has any changes
    in any attributes other than the ones given in exclude.


    ::


        from sqlalchemy_continuum.sa_utils import has_changes


        user = User()

        has_changes(user, 'name')  # False

        user.name = 'someone'

        has_changes(user, 'name')  # True

        has_changes(user)  # True


    You can check multiple attributes as well.
    ::


        has_changes(user, ['age'])  # True

        has_changes(user, ['name', 'age'])  # True


    This function also supports excluding certain attributes.

    ::

        has_changes(user, exclude=['name'])  # False

        has_changes(user, exclude=['age'])  # True

    .. versionchanged: 0.26.6
        Added support for multiple attributes and exclude parameter.

    :param obj: SQLAlchemy declarative model object
    :param attrs: Names of the attributes
    :param exclude: Names of the attributes to exclude
    """
    if attrs:
        if isinstance(attrs, str):
            return (
                sa.inspect(obj)
                .attrs
                .get(attrs)
                .history
                .has_changes()
            )
        else:
            return any(has_changes(obj, attr) for attr in attrs)
    else:
        if exclude is None:
            exclude = []
        return any(
            attr.history.has_changes()
            for key, attr in sa.inspect(obj).attrs.items()
            if key not in exclude
        )


def identity(obj_or_class):
    """
    Return the identity of given sqlalchemy declarative model class or instance
    as a tuple. This differs from obj._sa_instance_state.identity in a way that
    it always returns the identity even if object is still in transient state (
    new object that is not yet persisted into database). Also for classes it
    returns the identity attributes.

    ::

        from sqlalchemy import inspect
        from sqlalchemy_continuum.sa_utils import identity


        user = User(name='John Matrix')
        session.add(user)
        identity(user)  # None
        inspect(user).identity  # None

        session.flush()  # User now has id but is still in transient state

        identity(user)  # (1,)
        inspect(user).identity  # None

        session.commit()

        identity(user)  # (1,)
        inspect(user).identity  # (1, )


    You can also use identity for classes::


        identity(User)  # (User.id, )

    .. versionadded: 0.21.0

    :param obj: SQLAlchemy declarative model object
    """
    return tuple(
        getattr(obj_or_class, column_key)
        for column_key in get_primary_key_columns(obj_or_class)
    )


def naturally_equivalent(obj, obj2):
    """
    Returns whether two given SQLAlchemy declarative instances are
    naturally equivalent (all their non-primary key properties are equivalent).


    ::

        from sqlalchemy_continuum.sa_utils import naturally_equivalent


        user = User(name='someone')
        user2 = User(name='someone')

        user == user2  # False

        naturally_equivalent(user, user2)  # True


    :param obj: SQLAlchemy declarative model object
    :param obj2: SQLAlchemy declarative model object to compare with `obj`
    """
    for column_key, column in sa.inspect(obj.__class__).columns.items():
        if column.primary_key:
            continue

        if not (getattr(obj, column_key) == getattr(obj2, column_key)):
            return False
    return True
