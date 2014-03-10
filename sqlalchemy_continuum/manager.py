from contextlib import contextmanager
from inflection import underscore, pluralize
import sqlalchemy as sa
from sqlalchemy_utils.functions import is_auto_assigned_date_column
from sqlalchemy_utils.types import TSVectorType
from .builder import Builder
from .fetcher import SubqueryFetcher, ValidityFetcher
from .transaction_log import TransactionLogFactory
from .unit_of_work import UnitOfWork
from .plugins import PluginCollection


class VersioningManager(object):
    """
    VersioningManager delegates versioning configuration operations to builder
    classes and the actual versioning to UnitOfWork class. Manager contains
    configuration options that act as defaults for all versioned classes.
    """
    def __init__(
        self,
        unit_of_work_cls=UnitOfWork,
        options={},
        plugins=None,
        builder=None
    ):
        self.uow = unit_of_work_cls(self)
        if builder is None:
            self.builder = Builder()
        else:
            self.builder = builder
        self.builder.manager = self

        self.reset()
        self.options = {
            'versioning': True,
            'base_classes': None,
            'table_name': '%s_history',
            'exclude': [],
            'include': [],
            'transaction_column_name': 'transaction_id',
            'end_transaction_column_name': 'end_transaction_id',
            'operation_type_column_name': 'operation_type',
            'relation_naming_function': lambda a: pluralize(underscore(a)),
            'strategy': 'validity'
        }
        if plugins is None:
            self.plugins = []
        else:
            self.plugins = plugins
        self.options.update(options)

    @property
    def plugins(self):
        return self._plugins

    @plugins.setter
    def plugins(self, plugin_collection):
        self._plugins = PluginCollection(plugin_collection)

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
            mapper,
            'instrument_class',
            self.builder.instrument_versioned_classes
        )
        sa.event.listen(
            mapper,
            'after_configured',
            self.builder.configure_versioned_classes
        )
