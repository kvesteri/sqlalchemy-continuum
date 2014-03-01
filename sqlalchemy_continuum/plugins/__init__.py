import six
import sqlalchemy as sa
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.associationproxy import association_proxy
from ..transaction_log import TransactionChangesBase, TransactionMetaBase


class ModelFactory(object):
    model_name = None

    def __init__(self, manager):
        self.manager = manager

    def __call__(self):
        """
        Create model class but only if it doesn't already exist
        in declarative model registry.
        """
        registry = self.manager.declarative_base._decl_class_registry
        if self.model_name not in registry:
            return self.create_class()
        return registry[self.model_name]


class TransactionChangesFactory(ModelFactory):
    model_name = 'TransactionChanges'

    def create_class(self):
        """
        Create TransactionChanges class.
        """
        class TransactionChanges(
            self.manager.declarative_base,
            TransactionChangesBase
        ):
            __tablename__ = 'transaction_changes'

        TransactionChanges.transaction_log = sa.orm.relationship(
            self.manager.transaction_log_cls,
            backref=sa.orm.backref(
                'changes',
            ),
            primaryjoin=(
                '%s.id == TransactionChanges.transaction_id' %
                self.manager.transaction_log_cls.__name__
            ),
            foreign_keys=[TransactionChanges.transaction_id]
        )
        return TransactionChanges


class TransactionMetaFactory(ModelFactory):
    model_name = 'TransactionMeta'

    def create_class(self):
        """
        Create TransactionMeta class.
        """
        class TransactionMeta(
            self.manager.declarative_base,
            TransactionMetaBase
        ):
            __tablename__ = 'transaction_meta'

        TransactionMeta.transaction_log = sa.orm.relationship(
            self.manager.transaction_log_cls,
            backref=sa.orm.backref(
                'meta_relation',
                collection_class=attribute_mapped_collection('key')
            ),
            primaryjoin=(
                '%s.id == TransactionMeta.transaction_id' %
                self.manager.transaction_log_cls.__name__
            ),
            foreign_keys=[TransactionMeta.transaction_id]
        )

        self.manager.transaction_log_cls.meta = association_proxy(
            'meta_relation',
            'value',
            creator=lambda key, value: TransactionMeta(key=key, value=value)
        )

        return TransactionMeta


class Plugin(object):
    def __init__(self, manager):
        self.manager = manager

    def before_instrument(self):
        pass

    def before_flush(self, uow, session):
        pass

    def after_history_class_built(self, parent_cls, history_cls):
        pass


class TransactionMetaPlugin(Plugin):
    def before_instrument(self):
        self.model_class = TransactionMetaFactory(self.manager)()

    def before_flush(self, uow, session):
        """
        Create transaction meta entries based on transaction meta context
        key-value pairs.

        :param session: SQLAlchemy session object
        """
        if (
            uow.tx_meta and
            (
                uow.changed_entities(session) or
                uow.pending_statements
            )
        ):
            for key, value in uow.tx_meta.items():
                if callable(value):
                    value = six.text_type(value())
                meta = uow.manager.transaction_meta_cls(
                    transaction_id=self.current_transaction_id,
                    key=key,
                    value=value
                )
                session.add(meta)


class TransactionChangesPlugin(Plugin):
    def before_instrument(self):
        self.model_class = TransactionChangesFactory(self.manager)()

    def before_flush(self, uow, session):
        """
        Create transaction changes entries based on all operations that
        occurred during this UnitOfWork. For each entity that has been affected
        by an operation during this UnitOfWork this method creates a new
        TransactionChanges object.

        :param session: SQLAlchemy session object
        """
        for entity in uow.changed_entities(session):
            changes = self.model_class(
                transaction_id=uow.current_transaction_id,
                entity_name=six.text_type(entity.__name__)
            )
            session.add(changes)

    def after_history_class_built(self, parent_cls, history_cls):
        """
        Builds a relationship between currently built history class and
        TransactionChanges class.

        :param tx_changes_class: TransactionChanges class
        """
        transaction_column = getattr(
            history_cls,
            self.manager.option(parent_cls, 'transaction_column_name')
        )

        # Only define changes relation if it doesn't already exist in
        # parent class.
        if not hasattr(history_cls, 'changes'):
            history_cls.changes = sa.orm.relationship(
                self.model_class,
                primaryjoin=(
                    self.model_class.transaction_id == transaction_column
                ),
                foreign_keys=[self.model_class.transaction_id],
                backref=self.manager.options['relation_naming_function'](
                    parent_cls.__name__
                )
            )
        parent_cls.__versioned__['transaction_changes'] = self.model_class
