from copy import copy
import sqlalchemy as sa
from sqlalchemy_utils.functions import primary_keys
from .builder import VersionedBuilder
from .expression_reflector import ClassExpressionReflector
from .version import VersionClassBase
from .versioned import Versioned


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

        # We need to check if versions relation was already set for parent
        # class.
        if not hasattr(self.model, 'versions'):
            self.model.versions = sa.orm.relationship(
                self.extension_class,
                primaryjoin=sa.and_(*conditions),
                foreign_keys=foreign_keys,
                lazy='dynamic',
                backref=sa.orm.backref('parent'),
                viewonly=True
            )

    def build_transaction_relationship(self, transaction_log_class):
        # Only define transaction relation if it doesn't already exist in
        # parent class.
        if not hasattr(self.extension_class, 'transaction'):
            self.extension_class.transaction = sa.orm.relationship(
                transaction_log_class,
            )

    def find_closest_versioned_parent(self):
        for class_ in self.model.__bases__:
            if class_ in Versioned.HISTORY_CLASS_MAP:
                return (Versioned.HISTORY_CLASS_MAP[class_], )

    def base_classes(self):
        parents = (
            self.find_closest_versioned_parent() or
            self.option('base_classes')
        )
        return parents + (VersionClassBase, )

    def build_model(self, table):
        if not self.option('base_classes'):
            raise Exception(
                'Missing __versioned__ base_classes option for model %s.'
                % self.model.__name__
            )
        mapper_args = {}
        if self.find_closest_versioned_parent():
            reflector = ClassExpressionReflector(self.model)
            inherit_condition = reflector(
                self.model.__mapper__.inherit_condition
            )
            mapper_args = {
                'inherit_condition': inherit_condition
            }
        return type(
            '%sHistory' % self.model.__name__,
            self.base_classes(),
            {
                '__table__': table,
                '__mapper_args__': mapper_args
            }
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
        Versioned.HISTORY_CLASS_MAP[self.model] = self.extension_class
