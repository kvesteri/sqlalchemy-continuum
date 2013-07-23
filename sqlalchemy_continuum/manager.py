from contextlib import contextmanager
from inflection import underscore, pluralize
from copy import copy
import sqlalchemy as sa
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy_utils.functions import declarative_base
from .model_builder import ModelBuilder
from .table_builder import TableBuilder
from .relationship_builder import RelationshipBuilder
from .transaction_log import TransactionLogBase, TransactionChangesBase
from .unit_of_work import UnitOfWork


class VersioningManager(object):
    """
    VersioningManager delegates versioning configuration operations to builder
    classes and the actual versioning to UnitOfWork class. Manager contains
    configuration options that act as defaults for all versioned classes.
    """
    def __init__(
        self,
        options={}
    ):
        self.uow = UnitOfWork(self)
        self.reset()
        self.options = {
            'versioning': True,
            'base_classes': None,
            'table_name': '%s_history',
            'exclude': [],
            'include': [],
            'transaction_log_base': TransactionLogBase,
            'transaction_column_name': 'transaction_id',
            'operation_type_column_name': 'operation_type',
            'relation_naming_function': lambda a: pluralize(underscore(a))
        }
        self.options.update(options)

    def reset(self):
        """
        Resets this manager's internal state.

        This method should be used in test cases that create models on the fly.
        Otherwise history_class_map and some other variables would be polluted
        by no more used model classes.
        """
        self.tables = {}
        self.pending_classes = []
        self.association_tables = set([])
        self.association_history_tables = set([])
        self.history_class_map = {}
        self.uow.reset()

        self.metadata = None

    @contextmanager
    def tx_context(self, **tx_context):
        """
        Assigns values for current transaction context. When committing
        transaction these values are assigned to transaction object attributes.

        :param tx_context: dictionary containing TransactionLog object
                           attribute names and values
        """
        old_tx_context = self.uow.tx_context
        self.uow.tx_context = tx_context
        yield
        self.uow.tx_context = old_tx_context

    def transaction_log_factory(self):
        """
        Creates TransactionLog class.
        """
        class TransactionLog(
            self.declarative_base,
            self.options['transaction_log_base']
        ):
            __tablename__ = 'transaction_log'
            meta = sa.Column(MutableDict.as_mutable(HSTORE))
            manager = self

        return TransactionLog

    def create_transaction_log(self):
        """
        Creates TransactionLog class but only if it doesn't already exist in
        declarative model registry.
        """
        if 'TransactionLog' not in self.declarative_base._decl_class_registry:
            return self.transaction_log_factory()
        return self.declarative_base._decl_class_registry['TransactionLog']

    def transaction_changes_factory(self):
        """
        Creates TransactionChanges class.

        :param transaction_log_class: TransactionLog class
        """
        class TransactionChanges(
            self.declarative_base,
            TransactionChangesBase
        ):
            __tablename__ = 'transaction_changes'

        TransactionChanges.transaction_log = sa.orm.relationship(
            self.transaction_log_cls,
            backref=sa.orm.backref(
                'changes'
            ),
            primaryjoin=(
                '%s.id == TransactionChanges.transaction_id' %
                self.transaction_log_cls.__name__
            ),
            foreign_keys=[TransactionChanges.transaction_id]
        )
        return TransactionChanges

    def create_transaction_changes(self):
        """
        Creates TransactionChanges class but only if it doesn't already exist
        in declarative model registry.

        :param transaction_log_class: TransactionLog class
        """
        if (
            'TransactionChanges' not in
            self.declarative_base._decl_class_registry
        ):
            return self.transaction_changes_factory()
        return self.declarative_base._decl_class_registry['TransactionChanges']

    def build_tables(self):
        """
        Build tables for history models based on classes that were collected
        during class instrumentation process.
        """
        for cls in self.pending_classes:
            if not self.option(cls, 'versioning'):
                continue

            inherited_table = None
            for class_ in self.tables:
                if (issubclass(cls, class_) and
                        cls.__table__ == class_.__table__):
                    inherited_table = self.tables[class_]
                    break

            builder = TableBuilder(
                self,
                cls.__table__,
                model=cls
            )
            if inherited_table is not None:
                self.tables[class_] = builder(inherited_table)
            else:
                table = builder()
                self.tables[cls] = table

    def build_models(self):
        """
        Build declarative history models based on classes that were collected
        during class instrumentation process.
        """
        if self.pending_classes:
            cls = self.pending_classes[0]
            self.declarative_base = declarative_base(cls)
            self.transaction_log_cls = self.create_transaction_log()
            self.transaction_changes_cls = self.create_transaction_changes()

            for cls in self.pending_classes:
                if not self.option(cls, 'versioning'):
                    continue

                if cls in self.tables:
                    builder = ModelBuilder(self, cls)
                    builder(
                        self.tables[cls],
                        self.transaction_log_cls,
                        self.transaction_changes_cls
                    )

    def build_relationships(self, history_classes):
        """
        Builds relationships for all history classes.

        :param history_classes: list of generated history classes
        """
        for cls in history_classes:
            if not self.option(cls, 'versioning'):
                continue

            for prop in cls.__mapper__.iterate_properties:
                if prop.key == 'versions':
                    continue
                builder = RelationshipBuilder(self, cls, prop)
                builder()

    def option(self, model, name):
        """
        Returns the option value for given model. If the option is not found
        from given model falls back to default values of this manager object.
        If the option is not found from this manager object either this method
        throws a KeyError.

        :param model: SQLAlchemy declarative object
        :param name: name of the versioning option
        """
        try:
            return model.__versioned__[name]
        except (AttributeError, KeyError):
            return self.options[name]

    def instrument_versioned_classes(self, mapper, cls):
        """
        Collects all versioned classes and adds them into pending_classes list.

        :mapper mapper: SQLAlchemy mapper object
        :cls cls: SQLAlchemy declarative class
        """
        if not self.options['versioning']:
            return

        if hasattr(cls, '__versioned__'):
            if (not cls.__versioned__.get('class')
                    and cls not in self.pending_classes):
                self.pending_classes.append(cls)
                self.metadata = cls.metadata

    def apply_class_configuration_listeners(self, mapper):
        """
        Applies class configuration listeners for given mapper.

        The listener work in two phases:

        1. Class instrumentation phase
            The first listeners listens to class instrumentation event and
            handles the collecting of versioned models and adds them to
            the pending_classes list.
        2. After class configuration phase
            The second listener listens to after class configuration event and
            handles the actual history model generation based on list that
            was collected during class instrumenation phase.

        :param mapper:
            SQLAlchemy mapper to apply the class configuration listeners to
        """
        sa.event.listen(
            mapper, 'instrument_class', self.instrument_versioned_classes
        )
        sa.event.listen(
            mapper, 'after_configured', self.configure_versioned_classes
        )

    def configure_versioned_classes(self):
        """
        Configures all versioned classes that were collected during
        instrumentation process. The configuration has 4 steps:

        1. Build tables for history models.
        2. Build the actual history model declarative classes.
        3. Build relationships between these models.
        4. Empty pending_classes list so that consecutive mapper configuration
           does not create multiple history classes
        5. Assign all versioned attributes to use active history.
        """
        if not self.options['versioning']:
            return

        self.build_tables()
        self.build_models()

        # Create copy of all pending versioned classes so that we can inspect
        # them later when creating relationships.
        pending_copy = copy(self.pending_classes)
        self.pending_classes = []
        self.build_relationships(pending_copy)

        for cls in pending_copy:
            # set the "active_history" flag
            for prop in cls.__mapper__.iterate_properties:
                getattr(cls, prop.key).impl.active_history = True
