import six
import sqlalchemy as sa

from .base import ModelFactory, Plugin


class TransactionChangesBase(object):
    transaction_id = sa.Column(
        sa.BigInteger,
        primary_key=True
    )
    entity_name = sa.Column(sa.Unicode(255), primary_key=True)


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
