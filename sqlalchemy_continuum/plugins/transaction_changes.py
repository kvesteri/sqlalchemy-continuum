"""
TransactionChanges provides way of keeping track efficiently which declarative
models were changed in given transaction. This can be useful when transactions
need to be queried afterwards for problems such as:

1. Find all transactions which affected `User` model.

2. Find all transactions which didn't affect models `Entity` and `Event`.

The plugin works in two ways. On class instrumentation phase this plugin
creates a special transaction model called `TransactionChanges`. This model is
associated with table called `transaction_changes`, which has only only two
fields: transaction_id and entity_name. If for example transaction consisted
of saving 5 new User entities and 1 Article entity, two new rows would be
inserted into transaction_changes table.

================    =================
transaction_id          entity_name
----------------    -----------------
233678                  User
233678                  Article
================    =================
"""
import six
import sqlalchemy as sa

from .base import Plugin
from ..factory import ModelFactory
from ..utils import option


class TransactionChangesFactory(ModelFactory):
    model_name = 'TransactionChanges'

    def create_class(self, manager):
        """
        Create TransactionChanges class.
        """
        if manager.options['native_versioning']:
            type_ = sa.String
        else:
            type_ = sa.BigInteger

        class TransactionChanges(manager.declarative_base):
            __tablename__ = 'transaction_changes'

            transaction_id = sa.Column(
                type_,
                primary_key=True,
                autoincrement=False
            )
            entity_name = sa.Column(sa.Unicode(255), primary_key=True)

        TransactionChanges.transaction = sa.orm.relationship(
            manager.transaction_cls,
            backref=sa.orm.backref(
                'changes',
            ),
            primaryjoin=(
                '%s.id == TransactionChanges.transaction_id' %
                manager.transaction_cls.__name__
            ),
            foreign_keys=[TransactionChanges.transaction_id]
        )
        return TransactionChanges


class TransactionChangesPlugin(Plugin):
    objects = None

    def after_build_tx_class(self, manager):
        self.model_class = TransactionChangesFactory()(manager)

    def after_build_models(self, manager):
        self.model_class = TransactionChangesFactory()(manager)

    def before_create_version_objects(self, uow, session):
        for entity in uow.operations.entities:
            params = uow.current_transaction.id, six.text_type(entity.__name__)
            changes = session.query(self.model_class).get(params)
            if not changes:
                changes = self.model_class(
                    transaction_id=uow.current_transaction.id,
                    entity_name=six.text_type(entity.__name__)
                )
                session.add(changes)

    def clear(self):
        self.objects = None

    def after_rollback(self, uow, session):
        self.clear()

    def ater_commit(self, uow, session):
        self.clear()

    def after_version_class_built(self, parent_cls, version_cls):
        transaction_column = getattr(
            version_cls,
            option(parent_cls, 'transaction_column_name')
        )

        # Only define changes relation if it doesn't already exist in
        # parent class.
        if not hasattr(version_cls, 'changes'):
            version_cls.changes = sa.orm.relationship(
                self.model_class,
                primaryjoin=(
                    self.model_class.transaction_id == transaction_column
                ),
                foreign_keys=[self.model_class.transaction_id]
            )
        parent_cls.__versioned__['transaction_changes'] = self.model_class
