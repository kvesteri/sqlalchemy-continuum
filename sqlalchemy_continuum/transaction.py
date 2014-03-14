from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.compiler import compiles
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

    def __init__(self, user=True, remote_addr=True):
        self.user = user
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

            if self.user:
                user_id = sa.Column(
                    sa.Integer,
                    sa.ForeignKey('user.id'),
                    index=True
                )

                user = sa.orm.relationship('User')
        return Transaction
