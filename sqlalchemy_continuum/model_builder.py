from copy import copy
import six
import sqlalchemy as sa
from sqlalchemy_utils.functions import declarative_base
from .expression_reflector import ClassExpressionReflector
from .utils import option
from .version import VersionClassBase


class ModelBuilder(object):
    """
    VersionedModelBuilder handles the building of Version models based on
    parent table attributes and versioning configuration.
    """
    def __init__(self, versioning_manager, model):
        """
        :param versioning_manager:
            VersioningManager object
        :param model:
            SQLAlchemy declarative model object that acts as a parent for the
            built version model
        """
        self.manager = versioning_manager
        self.model = model

    def build_parent_relationship(self):
        """
        Builds a relationship between currently built version class and
        parent class (the model whose history the currently build version
        class represents).
        """
        conditions = []
        foreign_keys = []
        for key, column in sa.inspect(self.model).columns.items():
            if column.primary_key:
                conditions.append(
                    getattr(self.model, key)
                    ==
                    getattr(self.version_class, key)
                )
                foreign_keys.append(
                    getattr(self.version_class, key)
                )

        # We need to check if versions relation was already set for parent
        # class.
        if not hasattr(self.model, 'versions'):
            self.model.versions = sa.orm.relationship(
                self.version_class,
                primaryjoin=sa.and_(*conditions),
                foreign_keys=foreign_keys,
                order_by=lambda: getattr(
                    self.version_class,
                    option(self.model, 'transaction_column_name')
                ),
                lazy='dynamic',
                backref=sa.orm.backref(
                    'version_parent'
                ),
                viewonly=True
            )

    def build_transaction_relationship(self, tx_log_class):
        """
        Builds a relationship between currently built version class and
        Transaction class.

        :param tx_log_class: Transaction class
        """
        # Only define transaction relation if it doesn't already exist in
        # parent class.

        backref_name = option(self.model, 'relation_naming_function')(
            self.model.__name__
        )

        transaction_column = getattr(
            self.version_class,
            option(self.model, 'transaction_column_name')
        )

        if not hasattr(self.version_class, 'transaction'):
            self.version_class.transaction = sa.orm.relationship(
                tx_log_class,
                primaryjoin=tx_log_class.id == transaction_column,
                foreign_keys=[transaction_column],
                backref=backref_name
            )
        else:
            setattr(
                tx_log_class,
                backref_name,
                sa.orm.relationship(
                    self.version_class,
                    primaryjoin=tx_log_class.id == transaction_column,
                    foreign_keys=[transaction_column]
                )
            )

    def find_closest_versioned_parent(self):
        """
        Finds the closest versioned parent for current parent model.
        """
        for class_ in self.model.__bases__:
            if class_ in self.manager.version_class_map:
                return (self.manager.version_class_map[class_], )

    def base_classes(self):
        """
        Returns all base classes for history model.
        """
        parents = (
            self.find_closest_versioned_parent()
            or option(self.model, 'base_classes')
            or (declarative_base(self.model), )
        )
        return parents + (VersionClassBase, )

    def copy_polymorphism_args(self):
        args = {}
        if hasattr(self.model, '__mapper_args__'):
            arg_names = (
                'with_polymorphic',
                'polymorphic_identity',
                'concrete',
                'order_by'
            )
            for arg in arg_names:
                if arg in self.model.__mapper_args__:
                    args[arg] = (
                        self.model.__mapper_args__[arg]
                    )

            if 'polymorphic_on' in self.model.__mapper_args__:
                column = self.model.__mapper_args__['polymorphic_on']
                if isinstance(column, six.string_types):
                    args['polymorphic_on'] = column
                else:
                    args['polymorphic_on'] = column.key
        return args

    def inheritance_args(self, table):
        """
        Return mapper inheritance args for currently built history model.
        """
        args = {}
        parent_tuple = self.find_closest_versioned_parent()
        if parent_tuple:
            # The version classes do not contain foreign keys, hence we need
            # to map inheritance condition manually for classes that use
            # joined table inheritance
            parent = parent_tuple[0]

            if parent.__table__.name != table.name:
                reflector = ClassExpressionReflector(self.model)
                mapper = sa.inspect(self.model)
                inherit_condition = reflector(mapper.inherit_condition)

                args['inherit_condition'] = sa.and_(
                    inherit_condition,
                    '%s.transaction_id = %s_version.transaction_id' % (
                        parent.__table__.name,
                        self.model.__table__.name
                    )
                )
        args.update(self.copy_polymorphism_args())

        return args

    def build_model(self, table):
        """
        Build history model class.
        """
        mapper_args = {}
        mapper_args.update(self.inheritance_args(table))
        args = {
            '__mapper_args__': mapper_args
        }
        if not sa.inspect(self.model).single:
            args['__table__'] = table

        return type(
            '%sVersion' % self.model.__name__,
            self.base_classes(),
            args
        )

    def __call__(self, table, tx_log_class):
        """
        Build history model and relationships to parent model, transaction
        log model.
        """
        # versioned attributes need to be copied for each child class,
        # otherwise each child class would share the same __versioned__
        # option dict
        self.model.__versioned__ = copy(self.model.__versioned__)
        self.model.__versioning_manager__ = self.manager
        self.version_class = self.build_model(table)
        self.build_parent_relationship()
        self.build_transaction_relationship(tx_log_class)
        self.version_class.__versioning_manager__ = self.manager
        self.manager.version_class_map[self.model] = self.version_class
        self.manager.parent_class_map[self.version_class] = self.model
        return self.version_class
