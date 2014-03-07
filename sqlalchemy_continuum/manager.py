from contextlib import contextmanager
from inflection import underscore, pluralize
from copy import copy
import sqlalchemy as sa
from sqlalchemy_utils.functions import (
    declarative_base, is_auto_assigned_date_column
)
from sqlalchemy_utils.types import TSVectorType
from .fetcher import SubqueryFetcher, ValidityFetcher
from .model_builder import ModelBuilder
from .table_builder import TableBuilder
from .relationship_builder import RelationshipBuilder
from .transaction_log import TransactionLogFactory
from .unit_of_work import UnitOfWork
from .plugins import (
    PluginCollection,
    TransactionChangesPlugin,
    TransactionMetaPlugin
)


class VersioningManager(object):
    """
    VersioningManager delegates versioning configuration operations to builder
    classes and the actual versioning to UnitOfWork class. Manager contains
    configuration options that act as defaults for all versioned classes.
    """
    def __init__(
        self,
        unit_of_work_cls=UnitOfWork,
        options={}
    ):
        self.uow = unit_of_work_cls(self)
        self.reset()
        self.options = {
            'versioning': True,
            'base_classes': None,
            'table_name': '%s_history',
            'exclude': [],
            'include': [],
            'plugins': [
                TransactionChangesPlugin,
                TransactionMetaPlugin
            ],
            'transaction_column_name': 'transaction_id',
            'end_transaction_column_name': 'end_transaction_id',
            'operation_type_column_name': 'operation_type',
            'relation_naming_function': lambda a: pluralize(underscore(a)),
            'strategy': 'validity'
        }
        self._plugins = []
        self.options.update(options)

    @property
    def plugins(self):
        if not self._plugins:
            self._plugins = PluginCollection([
                plugin_class(self) for plugin_class in self.options['plugins']
            ])
        return self._plugins

    def fetcher(self, obj):
        if self.option(obj, 'strategy') == 'subquery':
            return SubqueryFetcher(self)
        else:
            return ValidityFetcher(self)

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
        self.declarative_base = None
        self.transaction_log_cls = None
        self.history_class_map = {}
        self.parent_class_map = {}
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

    @contextmanager
    def tx_meta(self, **tx_meta):
        """
        Assigns values for current transaction meta. When committing
        transaction new TransactionMeta records are created for each key-value
        pair.

        :param tx_context:
            dictionary containing key-value meta attribute pairs.
        """
        old_tx_meta = self.uow.tx_meta
        self.uow.tx_meta = tx_meta
        yield
        self.uow.tx_meta = old_tx_meta

    def create_transaction_log(self):
        """
        Create TransactionLog class but only if it doesn't already exist in
        declarative model registry.
        """
        return TransactionLogFactory(self)()

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

    def closest_matching_table(self, model):
        """
        Returns the closest matching table from the generated tables dictionary
        for given model. First tries to fetch an exact match for given model.
        If no table was found then tries to match given model as a subclass.

        :param model: SQLAlchemy declarative model class.
        """
        if model in self.tables:
            return self.tables[model]
        for cls in self.tables:
            if issubclass(model, cls):
                return self.tables[cls]

    def build_models(self):
        """
        Build declarative history models based on classes that were collected
        during class instrumentation process.
        """
        if self.pending_classes:
            cls = self.pending_classes[0]
            self.declarative_base = declarative_base(cls)
            self.create_transaction_log()
            self.plugins.after_build_tx_class()

            for cls in self.pending_classes:
                if not self.option(cls, 'versioning'):
                    continue

                table = self.closest_matching_table(cls)
                if table is not None:
                    builder = ModelBuilder(self, cls)
                    history_cls = builder(
                        table,
                        self.transaction_log_cls
                    )
                    self.plugins.after_history_class_built(cls, history_cls)

        self.plugins.after_build_models()

    def build_relationships(self, history_classes):
        """
        Builds relationships for all history classes.

        :param history_classes: list of generated history classes
        """
        for cls in history_classes:
            if not self.option(cls, 'versioning'):
                continue

            for prop in sa.inspect(cls).iterate_properties:
                if prop.key == 'versions':
                    continue
                builder = RelationshipBuilder(self, cls, prop)
                builder()

    def is_excluded_column(self, model, column):
        """
        Returns whether or not given column of given model is excluded from
        the associated history model.

        :param model: SQLAlchemy declarative model object.
        :param column: SQLAlchemy Column object.
        """
        if column.name in self.option(model, 'include'):
            return False
        return (
            column.name in self.option(model, 'exclude')
            or
            is_auto_assigned_date_column(column)
            or
            isinstance(column.type, TSVectorType)
        )

    def option(self, model, name):
        """
        Returns the option value for given model. If the option is not found
        from given model falls back to default values of this manager object.
        If the option is not found from this manager object either this method
        throws a KeyError.

        :param model: SQLAlchemy declarative object
        :param name: name of the versioning option
        """
        if not hasattr(model, '__versioned__'):
            raise TypeError('Model %r is not versioned.' % model)
        try:
            return model.__versioned__[name]
        except KeyError:
            return self.options[name]

    def instrument_versioned_classes(self, mapper, cls):
        """
        Collect versioned class and add it to pending_classes list.

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

        self._plugins = []

        self.build_tables()
        self.build_models()

        # Create copy of all pending versioned classes so that we can inspect
        # them later when creating relationships.
        pending_copy = copy(self.pending_classes)
        self.pending_classes = []
        self.build_relationships(pending_copy)

        for cls in pending_copy:
            # set the "active_history" flag
            for prop in sa.inspect(cls).iterate_properties:
                getattr(cls, prop.key).impl.active_history = True
