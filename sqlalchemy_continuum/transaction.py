from datetime import datetime

import six
import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles

from .exc import ImproperlyConfigured
from .factory import ModelFactory


@compiles(sa.types.BigInteger, 'sqlite')
def compile_big_integer(element, compiler, **kw):
    return 'INTEGER'


class TransactionBase(object):
    id = sa.Column(sa.types.BigInteger, primary_key=True, autoincrement=True)
    issued_at = sa.Column(sa.DateTime, default=datetime.utcnow)

    @property
    def entity_names(self):
        """
        Return a list of entity names that changed during this transaction.
        """
        return [changes.entity_name for changes in self.changes]

    @property
    def changed_entities(self):
        """
        Return all changed entities for this transaction log entry.

        Entities are returned as a dict where keys are entity classes and
        values lists of entitites that changed in this transaction.
        """
        manager = self.__versioning_manager__
        tuples = set(manager.version_class_map.items())
        entities = []

        for class_, version_class in tuples:

            if class_.__name__ not in self.entity_names:
                continue

            try:
                value = getattr(
                    self,
                    manager.options['relation_naming_function'](
                        class_.__name__
                    )
                )
            except AttributeError:
                continue

            if value:
                entities.append((
                    version_class,
                    value
                ))
        return dict(entities)


class TransactionFactory(ModelFactory):
    model_name = 'Transaction'

    def __init__(self, remote_addr=True):
        self.remote_addr = remote_addr

    def create_class(self, manager):
        """
        Create Transaction class.
        """
        class Transaction(
            manager.declarative_base,
            TransactionBase
        ):
            __tablename__ = 'transaction'
            __versioning_manager__ = manager

            if self.remote_addr:
                remote_addr = sa.Column(sa.String(50))

            if manager.user_cls:
                user_cls = manager.user_cls
                registry = manager.declarative_base._decl_class_registry

                if isinstance(user_cls, six.string_types):
                    try:
                        user_cls = registry[user_cls]
                    except KeyError:
                        raise ImproperlyConfigured(
                            'Could not build relationship between Transaction'
                            ' and %s. %s was not found in declarative class '
                            'registry. Either configure VersioningManager to '
                            'use different user class or disable this '
                            'relationship ' % (user_cls, user_cls)
                        )
                user_id = sa.Column(
                    sa.Integer,
                    sa.ForeignKey(
                        '%s.id' % user_cls.__tablename__
                    ),
                    index=True
                )

                user = sa.orm.relationship(user_cls)
        return Transaction
