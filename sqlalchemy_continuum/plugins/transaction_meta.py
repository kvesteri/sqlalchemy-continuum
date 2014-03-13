import sqlalchemy as sa
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.associationproxy import association_proxy

from .base import Plugin
from ..factory import ModelFactory


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

        TransactionMeta.transaction = sa.orm.relationship(
            self.manager.transaction_cls,
            backref=sa.orm.backref(
                'meta_relation',
                collection_class=attribute_mapped_collection('key')
            ),
            primaryjoin=(
                '%s.id == TransactionMeta.transaction_id' %
                self.manager.transaction_cls.__name__
            ),
            foreign_keys=[TransactionMeta.transaction_id]
        )

        self.manager.transaction_cls.meta = association_proxy(
            'meta_relation',
            'value',
            creator=lambda key, value: TransactionMeta(key=key, value=value)
        )

        return TransactionMeta


class TransactionMetaPlugin(Plugin):
    def after_build_tx_class(self, manager):
        self.model_class = TransactionMetaFactory(manager)()
        manager.transaction_meta_cls = self.model_class

    def after_build_models(self, manager):
        self.model_class = TransactionMetaFactory(manager)()
        manager.transaction_meta_cls = self.model_class
