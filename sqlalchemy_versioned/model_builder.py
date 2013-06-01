from copy import copy
import sqlalchemy as sa
from sqlalchemy_utils.functions import primary_keys
from .builder import VersionedBuilder


class VersionClassBase(object):
    def reify(self):
        for key, attr in self.__mapper__.class_manager.items():
            if key not in ['transaction', 'transaction_id']:
                setattr(self.parent, key, getattr(self, key))


class VersionedModelBuilder(VersionedBuilder):
    def build_parent_relationship(self):
        conditions = []
        foreign_keys = []
        for primary_key in primary_keys(self.model):
            conditions.append(
                getattr(self.model, primary_key.name)
                ==
                getattr(self.extension_class, primary_key.name)
            )
            foreign_keys.append(
                getattr(self.extension_class, primary_key.name)
            )

        self.model.versions = sa.orm.relationship(
            self.extension_class,
            primaryjoin=sa.and_(*conditions),
            foreign_keys=foreign_keys,
            lazy='dynamic',
            backref=sa.orm.backref('parent'),
            viewonly=True
        )

    def build_transaction_relationship(self, transaction_log_class):
        self.extension_class.transaction = sa.orm.relationship(
            transaction_log_class,
        )

    def build_model(self, table):
        if not self.option('base_classes'):
            raise Exception(
                'Missing __versioned__ base_classes option for model %s.'
                % self.model.__name__
            )

        return type(
            '%sHistory' % self.model.__name__,
            self.option('base_classes') + (VersionClassBase, ),
            {'__table__': table}
        )

    def __call__(self, table, transaction_log_class):
        # versioned attributes need to be copied for each child class,
        # otherwise each child class would share the same __versioned__
        # option dict
        self.model.__versioned__ = copy(self.model.__versioned__)
        self.model.__versioned__['transaction_log'] = transaction_log_class
        self.extension_class = self.build_model(table)
        self.build_parent_relationship()
        self.build_transaction_relationship(transaction_log_class)
        self.model.__versioned__['class'] = self.extension_class
        self.extension_class.__parent_class__ = self.model
