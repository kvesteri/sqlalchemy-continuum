"""
The ActivityPlugin is the most powerful plugin for tracking changes of
individual entities. If you use ActivityPlugin you probably don't need to use
TransactionChanges nor TransactionMeta plugins.

You can initialize the ActivityPlugin by adding it to versioning manager.

::

    activity_plugin = ActivityPlugin()

    make_versioned(plugins=[activity_plugin])


ActivityPlugin uses single database table for tracking activities. This table
follows the data structure in `activity stream specification`_, but it comes
with a nice twist:

    ==============  =========== =============
    Column          Type        Description
    ==============  =========== =============
    id              BigInteger  The primary key of the activity
    verb            Unicode     Verb defines the action of the activity
    data            JSON        Additional data for the activity in JSON format
    transaction_id  BigInteger  The transaction this activity was associated
                                with
    object_id       BigInteger  The primary key of the object. Object can be
                                any entity which has an integer as primary key.
    object_type     Unicode     The type of the object (class name as string)

    object_tx_id    BigInteger  The last transaction_id associated with the
                                object. This is used for efficiently fetching
                                the object version associated with this
                                activity.

    target_id       BigInteger  The primary key of the target. Target can be
                                any entity which has an integer as primary key.
    target_type     Unicode     The of the target (class name as string)

    target_tx_id    BigInteger  The last transaction_id associated with the
                                target.
    ==============  =========== =============


Each Activity has relationships to actor, object and target but it also holds
information about the associated transaction and about the last associated
transactions with the target and object. This allows each activity to also have
object_version and target_version relationships for introspecting what those
objects and targets were in given point in time. All these relationship
properties use `generic relationships`_ ported from the SQLAlchemy-Utils
package.

Limitations
^^^^^^^^^^^

Currently all changes to parent models must be flushed or committed before
creating activities. This is due to a fact that there is still no dependency
processors for generic relationships. So when you create activities and assign
objects / targets for those please remember to flush the session before
creating an activity::


    article = Article(name=u'Some article')
    session.add(article)
    session.flush()  # <- IMPORTANT!
    first_activity = Activity(verb=u'create', object=article)
    session.add(first_activity)
    session.commit()


Targets and objects of given activity must have an integer primary key
column id.


Create activities
^^^^^^^^^^^^^^^^^


Once your models have been configured you can get the Activity model from the
ActivityPlugin class with activity_cls property::


    Activity = activity_plugin.activity_cls


Now let's say we have model called Article and Category. Each Article has one
Category. Activities should be created along with the changes you make on
these models. ::

    article = Article(name=u'Some article')
    session.add(article)
    session.flush()
    first_activity = Activity(verb=u'create', object=article)
    session.add(first_activity)
    session.commit()


Current transaction gets automatically assigned to activity object::

    first_activity.transaction  # Transaction object


Update activities
^^^^^^^^^^^^^^^^^

The object property of the Activity object holds the current object and the
object_version holds the object version at the time when the activity was
created. ::


    article.name = u'Some article updated!'
    session.flush()
    second_activity = Activity(verb=u'update', object=article)
    session.add(second_activity)
    session.commit()

    second_activity.object.name  # u'Some article updated!'
    first_activity.object.name  # u'Some article updated!'

    first_activity.object_version.name  # u'Some article'


Delete activities
^^^^^^^^^^^^^^^^^


The version properties are especially useful for delete activities. Once the
activity is fetched from the database the object is no longer available (
since its deleted), hence the only way we could show some information about the
object the user deleted is by accessing the object_version property.

::


    session.delete(article)
    session.flush()
    third_activity = Activity(verb=u'delete', object=article)
    session.add(third_activity)
    session.commit()

    third_activity.object_version.name  # u'Some article updated!'


Local version histories using targets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The target property of the Activity model offers a way of tracking changes of
given related object. In the example below we create a new activity when adding
a category for article and then mark the article as the target of this
activity.



::


    session.add(Category(name=u'Fist category', article=article))
    session.flush()
    activity = Activity(
        verb=u'create',
        object=category,
        target=article
    )
    session.add(activity)
    session.commit()


Now if we wanted to find all the changes that affected given article we could
do so by searching through all the activities where either the object or
target is the given article.


::

    import sqlalchemy as sa


    activities = session.query(Activity).filter(
        sa.or_(
            Activity.object == article,
            Activity.target == article
        )
    )



.. _activity stream specification:
    https://www.activitystrea.ms
.. _generic relationships:
    https://sqlalchemy-utils.readthedocs.io/en/latest/generic_relationship.html
"""
from collections.abc import Iterable
import json

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import ColumnProperty, class_mapper
from sqlalchemy.orm.attributes import (
    ScalarAttributeImpl,
    register_attribute,
)
from sqlalchemy.orm.base import PASSIVE_OFF
from sqlalchemy.orm.interfaces import MapperProperty, PropComparator
from sqlalchemy.orm.session import _state_session
from sqlalchemy.util import set_creation_order

from .base import Plugin
from ..factory import ModelFactory
from ..sa_utils import identity
from ..utils import version_class, version_obj


try:
    from sqlalchemy.dialects.postgresql import JSON
    has_postgres_json = True
except ImportError:
    class PostgresJSONType(sa.types.UserDefinedType):
        """
        Text search vector type for postgresql.
        """
        def get_col_spec(self):
            return 'json'

    ischema_names['json'] = PostgresJSONType
    has_postgres_json = False

def _get_class_registry(class_):
    try:
        return class_.registry._class_registry
    except AttributeError:  # SQLAlchemy <1.4
        return class_._decl_class_registry


class ActivityBase(object):
    id = sa.Column(
        sa.BigInteger,
        sa.schema.Sequence('activity_id_seq'),
        primary_key=True,
        autoincrement=True
    )

    verb = sa.Column(sa.Unicode(255))

    @hybrid_property
    def actor(self):
        return self.transaction.user


class ActivityFactory(ModelFactory):
    model_name = 'Activity'

    def create_class(self, manager):
        """
        Create Activity class.
        """
        class Activity(
            manager.declarative_base,
            ActivityBase
        ):
            __tablename__ = 'activity'
            manager = self

            transaction_id = sa.Column(
                sa.BigInteger,
                index=True,
                nullable=False
            )

            data = sa.Column(JSONType)

            object_type = sa.Column(sa.String(255))

            object_id = sa.Column(sa.BigInteger)

            object_tx_id = sa.Column(sa.BigInteger)

            target_type = sa.Column(sa.String(255))

            target_id = sa.Column(sa.BigInteger)

            target_tx_id = sa.Column(sa.BigInteger)

            def _calculate_tx_id(self, obj):
                session = sa.orm.object_session(self)
                if obj:
                    object_version = version_obj(session, obj)
                    if object_version:
                        return object_version.transaction_id

                    model = obj.__class__
                    version_cls = version_class(model)
                    primary_key = inspect(model).primary_key[0].name
                    return session.query(
                        sa.func.max(version_cls.transaction_id)
                    ).filter(
                        getattr(version_cls, primary_key) == getattr(obj, primary_key)
                    ).scalar()

            def calculate_object_tx_id(self):
                self.object_tx_id = self._calculate_tx_id(self.object)

            def calculate_target_tx_id(self):
                self.target_tx_id = self._calculate_tx_id(self.target)

            object = generic_relationship(
                object_type, object_id
            )

            @hybrid_property
            def object_version_type(self):
                return self.object_type + 'Version'

            @object_version_type.expression
            def object_version_type(cls):
                return sa.func.concat(cls.object_type, 'Version')

            object_version = generic_relationship(
                object_version_type, (object_id, object_tx_id)
            )

            target = generic_relationship(
                target_type, target_id
            )

            @hybrid_property
            def target_version_type(self):
                return self.target_type + 'Version'

            @target_version_type.expression
            def target_version_type(cls):
                return sa.func.concat(cls.target_type, 'Version')

            target_version = generic_relationship(
                target_version_type, (target_id, target_tx_id)
            )

        Activity.transaction = sa.orm.relationship(
            manager.transaction_cls,
            backref=sa.orm.backref(
                'activities',
            ),
            primaryjoin=(
                '%s.id == Activity.transaction_id' %
                manager.transaction_cls.__name__
            ),
            foreign_keys=[Activity.transaction_id]
        )
        return Activity


class ActivityPlugin(Plugin):
    activity_cls = None

    def after_build_models(self, manager):
        self.activity_cls = ActivityFactory()(manager)
        manager.activity_cls = self.activity_cls

    def is_session_modified(self, session):
        """
        Return that the session has been modified if the session contains an
        activity class.

        :param session: SQLAlchemy session object
        """
        return any(isinstance(obj, self.activity_cls) for obj in session)

    def before_flush(self, uow, session):
        for obj in session:
            if isinstance(obj, self.activity_cls):
                obj.transaction = uow.current_transaction
                obj.calculate_target_tx_id()
                obj.calculate_object_tx_id()

    def after_version_class_built(self, parent_cls, version_cls):
        pass


class GenericAttributeImpl(ScalarAttributeImpl):
    def __init__(self, *args, **kwargs):
        """
        The constructor of attributes.AttributeImpl changed in SQLAlchemy 2.0.22,
        adding a 'default_function' required positional argument before 'dispatch'.
        This adjustment ensures compatibility across versions by inserting None for
        'default_function' in versions >= 2.0.22.

        Arguments received: (class, key, dispatch)
        Required by AttributeImpl: (class, key, default_function, dispatch)
        Setting None as default_function here.
        """
        # Adjust for SQLAlchemy version change
        sqlalchemy_version = tuple(map(int, sa.__version__.split('.')))
        if sqlalchemy_version >= (2, 0, 22):
            args = (*args[:2], None, *args[2:])

        super().__init__(*args, **kwargs)

    def get(self, state, dict_, passive=PASSIVE_OFF):
        if self.key in dict_:
            return dict_[self.key]

        # Retrieve the session bound to the state in order to perform
        # a lazy query for the attribute.
        # TODO: replace this with sa.orm.session.object_session?
        session = _state_session(state)
        if session is None:
            # State is not bound to a session; we cannot proceed.
            return None

        # Find class for discriminator.
        # TODO: Perhaps optimize with some sort of lookup?
        discriminator = self.get_state_discriminator(state)
        target_class = _get_class_registry(state.class_).get(discriminator)

        if target_class is None:
            # Unknown discriminator; return nothing.
            return None

        id = self.get_state_id(state)

        try:
            target = session.get(target_class, id)
        except AttributeError:
            # sqlalchemy 1.3
            target = session.query(target_class).get(id)

        # Return found (or not found) target.
        return target

    def get_state_discriminator(self, state):
        discriminator = self.parent_token.discriminator
        if isinstance(discriminator, hybrid_property):
            return getattr(state.obj(), discriminator.__name__)
        else:
            return state.attrs[discriminator.key].value

    def get_state_id(self, state):
        # Lookup row with the discriminator and id.
        return tuple(state.attrs[id.key].value for id in self.parent_token.id)

    def set(self, state, dict_, initiator,
            passive=PASSIVE_OFF,
            check_old=None,
            pop=False):

        # Set us on the state.
        dict_[self.key] = initiator

        if initiator is None:
            # Nullify relationship args
            for id in self.parent_token.id:
                dict_[id.key] = None
            dict_[self.parent_token.discriminator.key] = None
        else:
            # Get the primary key of the initiator and ensure we
            # can support this assignment.
            class_ = type(initiator)
            mapper = class_mapper(class_)

            pk = mapper.identity_key_from_instance(initiator)[1]

            # Set the identifier and the discriminator.
            discriminator = class_.__name__

            for index, id in enumerate(self.parent_token.id):
                dict_[id.key] = pk[index]
            dict_[self.parent_token.discriminator.key] = discriminator


class GenericRelationshipProperty(MapperProperty):
    """A generic form of the relationship property.

    Creates a 1 to many relationship between the parent model
    and any other models using a discriminator (the table name).

    :param discriminator
        Field to discriminate which model we are referring to.
    :param id:
        Field to point to the model we are referring to.
    """

    def __init__(self, discriminator, id, doc=None):
        super().__init__()
        self._discriminator_col = discriminator
        self._id_cols = id
        self._id = None
        self._discriminator = None
        self.doc = doc

        set_creation_order(self)

    def _column_to_property(self, column):
        if isinstance(column, hybrid_property):
            attr_key = column.__name__
            for key, attr in self.parent.all_orm_descriptors.items():
                if key == attr_key:
                    return attr
        else:
            for attr in self.parent.attrs.values():
                if isinstance(attr, ColumnProperty):
                    if attr.columns[0].name == column.name:
                        return attr

    def init(self):
        def convert_strings(column):
            if isinstance(column, str):
                return self.parent.columns[column]
            return column

        self._discriminator_col = convert_strings(self._discriminator_col)
        self._id_cols = convert_strings(self._id_cols)

        if isinstance(self._id_cols, Iterable):
            self._id_cols = list(map(convert_strings, self._id_cols))
        else:
            self._id_cols = [self._id_cols]

        self.discriminator = self._column_to_property(self._discriminator_col)

        if self.discriminator is None:
            raise ImproperlyConfigured(
                'Could not find discriminator descriptor.'
            )

        self.id = list(map(self._column_to_property, self._id_cols))

    class Comparator(PropComparator):
        def __init__(self, prop, parentmapper):
            self.property = prop
            self._parententity = parentmapper

        def __eq__(self, other):
            discriminator = type(other).__name__
            q = self.property._discriminator_col == discriminator
            other_id = identity(other)
            for index, id in enumerate(self.property._id_cols):
                q &= id == other_id[index]
            return q

        def __ne__(self, other):
            return ~(self == other)

        def is_type(self, other):
            mapper = sa.inspect(other)
            # Iterate through the weak sequence in order to get the actual
            # mappers
            class_names = [other.__name__]
            class_names.extend([
                submapper.class_.__name__
                for submapper in mapper._inheriting_mappers
            ])

            return self.property._discriminator_col.in_(class_names)

    def instrument_class(self, mapper):
        register_attribute(
            mapper.class_,
            self.key,
            comparator=self.Comparator(self, mapper),
            parententity=mapper,
            doc=self.doc,
            impl_class=GenericAttributeImpl,
            parent_token=self
        )


class ImproperlyConfigured(Exception):
    """
    SQLAlchemy-Continuum is improperly configured; normally due to usage of
    a utility that depends on a missing library.
    """


class JSONType(sa.types.TypeDecorator):
    """
    JSONType offers way of saving JSON data structures to database. On
    PostgreSQL the underlying implementation of this data type is 'json' while
    on other databases its simply 'text'.

    ::


        from sqlalchemy_continuum.plugins.activity import JSONType


        class Product(Base):
            __tablename__ = 'product'
            id = sa.Column(sa.Integer, autoincrement=True)
            name = sa.Column(sa.Unicode(50))
            details = sa.Column(JSONType)


        product = Product()
        product.details = {
            'color': 'red',
            'type': 'car',
            'max-speed': '400 mph'
        }
        session.commit()
    """
    impl = sa.UnicodeText
    hashable = False
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super(JSONType, self).__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            # Use the native JSON type.
            if has_postgres_json:
                return dialect.type_descriptor(JSON())
            else:
                return dialect.type_descriptor(PostgresJSONType())
        else:
            return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value, dialect):
        if dialect.name == 'postgresql' and has_postgres_json:
            return value
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == 'postgresql':
            return value
        if value is not None:
            value = json.loads(value)
        return value


def generic_relationship(*args, **kwargs):
    return GenericRelationshipProperty(*args, **kwargs)
