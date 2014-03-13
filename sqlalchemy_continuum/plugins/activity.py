"""
Activity
--------
The ActivityPlugin is the most powerful plugin for tracking changes of
individual entities. If you use ActivityPlugin you probably don't need to use
TransactionChanges nor TransactionMeta plugins.

You can initalize the ActivityPlugin by adding it to versioning manager.

::

    make_versioned(plugins=[ActivityPlugin])


ActivityPlugin uses single database table for tracking activities. This table
follows the data structure in `activity stream specification`_, but it comes
with a nice twist:

    ==============  =========== ========================================
    Column          Type        Description
    --------------  ----------- ----------------------------------------
    id              BigInteger  The primary key of the activity
    verb            Unicode     Verb defines the action of the activity
    data            JSON        Additional data for the activity in JSON format
    transaction_id  BigInteger  The transaction this activity was associated
                                with
    object_id       BigInteger  The primary key of the object. Object can be
                                any entity which has an integer as primary key.
    object_type     Unicode     The type of the object (class name as string)

    object_transaction_id

                    BigInteger  The last transaction_id associated with the
                                object. This is used for efficiently fetching
                                the object version associated with this
                                activity.

    target_id       BigInteger  The primary key of the target. Target can be
                                any entity which has an integer as primary key.
    target_type     Unicode     The of the target (class name as string)

    target_transaction_id

                    BigInteger  The last transaction_id associated with the
                                target.
    ==============  =========== ========================================


Each Activity has relationships to actor, object and target but it also holds
information about the transaction when it was created. This allows each
activity to also have object_version and target_version relationships for
introspecting what those objects and targets were in given point in time.

.. _activity stream specification:
    http://www.activitystrea.ms
"""

import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import JSONType, generates, generic_relationship

from .base import Plugin
from ..factory import ModelFactory
from ..utils import version_class


class ActivityBase(object):
    id = sa.Column(sa.BigInteger, primary_key=True, autoincrement=True)

    verb = sa.Column(sa.Unicode(255))

    @hybrid_property
    def actor(self):
        self.transaction.user


class ActivityFactory(ModelFactory):
    model_name = 'Activity'

    def create_class(self):
        """
        Create Activity class.
        """
        class Activity(
            self.manager.declarative_base,
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

            object_transaction_id = sa.Column(sa.BigInteger)

            target_type = sa.Column(sa.String(255))

            target_id = sa.Column(sa.BigInteger)

            target_transaction_id = sa.Column(sa.BigInteger)

            @generates(object_transaction_id)
            def generate_object_transaction_id(self):
                session = sa.orm.object_session(self)
                if self.object:
                    version_cls = version_class(self.object.__class__)
                    return session.query(
                        sa.func.max(version_cls.transaction_id)
                    ).scalar()

            @generates(target_transaction_id)
            def generate_target_transaction_id(self):
                session = sa.orm.object_session(self)
                if self.target:
                    version_cls = version_class(self.target.__class__)
                    return session.query(
                        sa.func.max(version_cls.transaction_id)
                    ).scalar()

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
                object_version_type, (object_id, object_transaction_id)
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
                target_version_type, (target_id, target_transaction_id)
            )

        Activity.transaction = sa.orm.relationship(
            self.manager.transaction_cls,
            backref=sa.orm.backref(
                'activities',
            ),
            primaryjoin=(
                '%s.id == Activity.transaction_id' %
                self.manager.transaction_cls.__name__
            ),
            foreign_keys=[Activity.transaction_id]
        )
        return Activity


class ActivityPlugin(Plugin):
    def after_build_models(self, manager):
        self.model_class = ActivityFactory(manager)()
        manager.activity_cls = self.model_class

    def is_session_modified(self, session):
        """
        Return that the session has been modified if the session contains an
        activity class.

        :param session: SQLAlchemy session object
        """
        return any(isinstance(obj, self.model_class) for obj in session)

    def before_flush(self, uow, session):
        for obj in session:
            if isinstance(obj, self.model_class):
                obj.transaction = uow.current_transaction

    def after_version_class_built(self, parent_cls, version_cls):
        pass
