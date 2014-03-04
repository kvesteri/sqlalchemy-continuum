import six
import sqlalchemy as sa
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.associationproxy import association_proxy

from .base import ModelFactory, Plugin
from ..operation import IdentitySet


class TransactionMetaBase(object):
    transaction_id = sa.Column(
        sa.BigInteger,
        primary_key=True
    )
    key = sa.Column(sa.Unicode(255), primary_key=True)
    value = sa.Column(sa.UnicodeText)


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


class TransactionMetaPlugin(Plugin):
    objects = None

    def before_instrument(self):
        self.model_class = TransactionMetaFactory(self.manager)()
        self.manager.transaction_meta_cls = self.model_class

    def clear(self):
        self.objects = None

    def after_rollback(self, uow, session):
        self.clear()

    def after_commit(self, uow, session):
        self.clear()

    def before_flush(self, uow, session):
        """
        Create transaction meta entries based on transaction meta context
        key-value pairs.

        :param session: SQLAlchemy session object
        """
        if self.objects is None:
            self.objects = IdentitySet()
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
                meta = self.model_class(
                    transaction_id=uow.current_transaction.id,
                    key=key,
                    value=value
                )
                if meta not in self.objects:
                    self.objects.add(meta)
                    session.add(meta)
