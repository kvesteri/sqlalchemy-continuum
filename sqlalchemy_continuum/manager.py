import re
from functools import wraps

import sqlalchemy as sa
from sqlalchemy.orm import object_session
from sqlalchemy_utils import get_column_key

from .builder import Builder
from .fetcher import SubqueryFetcher, ValidityFetcher
from .operation import Operation
from .plugins import PluginCollection
from .transaction import TransactionFactory
from .unit_of_work import UnitOfWork
from .utils import is_modified, is_versioned


def tracked_operation(func):
    @wraps(func)
    def wrapper(self, mapper, connection, target):
        if not is_versioned(target):
            return
        session = object_session(target)
        conn = session.connection()
        try:
            uow = self.units_of_work[conn]
        except KeyError:
            uow = self.units_of_work[conn.engine]
        return func(self, uow, target)
    return wrapper


class VersioningManager(object):
    """
    VersioningManager delegates versioning configuration operations to builder
    classes and the actual versioning to UnitOfWork class. Manager contains
    configuration options that act as defaults for all versioned classes.

    :param unit_of_work_cls:
        The UnitOfWork class to use for initializing UnitOfWork objects for
        versioning
    :param transaction_cls:
        Transaction class to use for versioning. If None, the default
        Transaction class generated by TransactionFactory will be used.
    :param user_cls:
        User class which Transaction class should have relationship to. This
        can either be a class or string name of a class for lazy evaluation.
    :param options:
        Versioning options
    :param plugins:
        Versioning plugins that listen the events invoked by the manager.
    :param builder:
        Builder object which handles the building of versioning tables and
        models.
    """
    def __init__(
        self,
        unit_of_work_cls=UnitOfWork,
        transaction_cls=None,
        user_cls=None,
        options={},
        plugins=None,
        builder=None
    ):
        self.uow_class = unit_of_work_cls
        if builder is None:
            self.builder = Builder()
        else:
            self.builder = builder
        self.builder.manager = self
        self.reset()
        if transaction_cls is not None:
            self.transaction_cls = transaction_cls
        else:
            self.transaction_cls = TransactionFactory()
        if user_cls is not None:
            self.user_cls = user_cls

        self.options = {
            'versioning': True,
            'base_classes': None,
            'table_schema': None,
            'table_name': '%s_version',
            'exclude': [],
            'include': [],
            'native_versioning': False,
            'create_models': True,
            'create_tables': True,
            'transaction_column_name': 'transaction_id',
            'end_transaction_column_name': 'end_transaction_id',
            'operation_type_column_name': 'operation_type',
            'strategy': 'validity',
            'use_module_name': False
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
        self.association_tables = set()
        self.association_version_tables = set()
        self.declarative_base = None
        self.version_class_map = {}
        self.parent_class_map = {}
        self.session_listeners = {
            'before_flush': self.before_flush,
            'after_flush': self.after_flush,
            'after_commit': self.clear,
            'after_rollback': self.clear,
        }
        self.mapper_listeners = {
            'after_delete': self.track_deletes,
            'after_update': self.track_updates,
            'after_insert': self.track_inserts,
        }
        self.class_config_listeners = {
            'instrument_class': self.builder.instrument_versioned_classes,
            'after_configured': self.builder.configure_versioned_classes,
        }

        # A dictionary of units of work. Keys as connection objects and values
        # as UnitOfWork objects.
        self.units_of_work = {}

        self.session_connection_map = {}

        self.metadata = None

    def create_transaction_model(self):
        """
        Create Transaction class but only if it doesn't already exist in
        declarative model registry.
        """
        if isinstance(self.transaction_cls, TransactionFactory):
            self.transaction_cls = self.transaction_cls(self)
        return self.transaction_cls

    def is_excluded_column(self, model, column):
        try:
            key = get_column_key(model, column)
        except sa.orm.exc.UnmappedColumnError:
            return False

        return self.is_excluded_property(model, key)

    def is_excluded_property(self, model, key):
        """
        Returns whether or not given property of given model is excluded from
        the associated history model.

        :param model: SQLAlchemy declarative model object.
        :param key: Model property key
        """
        if key in self.option(model, 'include'):
            return False
        return key in self.option(model, 'exclude')

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
        for event_name, listener in self.class_config_listeners.items():
            sa.event.listen(mapper, event_name, listener)

    def remove_class_configuration_listeners(self, mapper):
        """
        Remove versioning class configuration listeners from specified mapper.

        :param mapper:
            mapper to remove class configuration listeners from
        """
        for event_name, listener in self.class_config_listeners.items():
            sa.event.remove(mapper, event_name, listener)

    def track_operations(self, mapper):
        """
        Attach listeners for specified mapper that track SQL inserts, updates
        and deletes.

        :param mapper: mapper to track the SQL operations from
        """
        for event_name, listener in self.mapper_listeners.items():
            sa.event.listen(mapper, event_name, listener)

    def remove_operations_tracking(self, mapper):
        """
        Remove listeners from specified mapper that track SQL inserts, updates
        and deletes.

        :param mapper:
            mapper to remove the SQL operations tracking listeners from
        """
        for event_name, listener in self.mapper_listeners.items():
            sa.event.remove(mapper, event_name, listener)

    def track_session(self, session):
        """
        Attach listeners that track the operations (flushing, committing and
        rolling back) of given session. This method should be used in
        conjuction with `track_operations`.

        :param session: SQLAlchemy session to track the operations from
        """
        for event_name, listener in self.session_listeners.items():
            sa.event.listen(session, event_name, listener)

    def remove_session_tracking(self, session):
        """
        Remove listeners that track the operations (flushing, committing and
        rolling back) of given session. This method should be used in
        conjuction with `remove_operations_tracking`.

        :param session:
            SQLAlchemy session to remove the operations tracking from
        """
        for event_name, listener in self.session_listeners.items():
            sa.event.remove(session, event_name, listener)

    @tracked_operation
    def track_inserts(self, uow, target):
        """
        Track object insert operations. Whenever object is inserted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        uow.operations.add_insert(target)

    @tracked_operation
    def track_updates(self, uow, target):
        """
        Track object update operations. Whenever object is updated it is
        added to this UnitOfWork's internal operations dictionary.
        """
        if not is_modified(target):
            return
        uow.operations.add_update(target)

    @tracked_operation
    def track_deletes(self, uow, target):
        """
        Track object deletion operations. Whenever object is deleted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        uow.operations.add_delete(target)

    def unit_of_work(self, session):
        """
        Return the associated SQLAlchemy-Continuum UnitOfWork object for given
        SQLAlchemy session object.

        If no UnitOfWork object exists for given object then this method tries
        to create one.

        :param session: SQLAlchemy session object
        """
        conn = session.connection()
        if conn not in self.session_connection_map.values():
            self.session_connection_map[session] = conn

        if conn in self.units_of_work:
            return self.units_of_work[conn]
        else:
            uow = self.uow_class(self)
            self.units_of_work[conn] = uow
            return uow

    def before_flush(self, session, flush_context, instances):
        """
        Before flush listener for SQLAlchemy sessions. If this manager has
        versioning enabled this listener invokes the process before flush of
        associated UnitOfWork object.

        :param session: SQLAlchemy session
        """
        if not self.options['versioning']:
            return

        uow = self.unit_of_work(session)
        uow.process_before_flush(session)

    def after_flush(self, session, flush_context):
        """
        After flush listener for SQLAlchemy sessions. If this manager has
        versioning enabled this listener gets the UnitOfWork associated with
        session's connections and invokes the process_after_flush method
        of that object.

        :param session: SQLAlchemy session
        """
        if not self.options['versioning']:
            return
        uow = self.unit_of_work(session)
        uow.process_after_flush(session)

    def clear(self, session):
        """
        Simple SQLAlchemy listener that is being invoked after succesful
        transaction commit or when transaction rollback occurs. The purpose of
        this listener is to reset this UnitOfWork back to its initialization
        state.

        :param session: SQLAlchemy session object
        """
        if session.transaction.nested:
            return
        conn = self.session_connection_map.pop(session, None)
        if conn in self.units_of_work:
            uow = self.units_of_work[conn]
            uow.reset(session)
            del self.units_of_work[conn]

    def append_association_operation(self, conn, table_name, params, op):
        """
        Append history association operation to pending_statements list.
        """
        table_schema = self.options.get('table_schema', None)
        version_table_name = (((table_schema + '.') if table_schema else '')
                              + self.options['table_name']) % table_name

        params['operation_type'] = op
        stmt = (
            self.metadata.tables[version_table_name]
            .insert()
            .values(params)
        )
        try:
            uow = self.units_of_work[conn]
        except KeyError:
            uow = self.units_of_work[conn.engine]
        uow.pending_statements.append(stmt)

    def track_association_operations(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        """
        Track association operations and adds the generated history
        association operations to pending_statements list.
        """
        if (
            not self.options['versioning'] and
            not self.options['native_versioning']
        ):
            return

        op = None
        if context.isinsert:
            op = Operation.INSERT
        elif context.isdelete:
            op = Operation.DELETE

        if op is not None:
            table_name = statement.split(' ')[2]
            table_names = [
                table.name for table in self.association_tables
            ]
            if table_name in table_names:
                if executemany:
                    # SQLAlchemy does not support function based values for
                    # multi-inserts, hence we need to convert the orignal
                    # multi-insert into batch of normal inserts
                    for params in parameters:
                        self.append_association_operation(
                            conn,
                            table_name,
                            self.positional_args_to_dict(
                                op, statement, params
                            ),
                            op
                        )
                else:
                    self.append_association_operation(
                        conn,
                        table_name,
                        self.positional_args_to_dict(
                            op,
                            statement,
                            parameters
                        ),
                        op
                    )

    def positional_args_to_dict(self, op, statement, params):
        """
        On some drivers (eg sqlite) generated INSERT statements use positional
        args instead of key value dictionary. This method converts positional
        args to key value dict.

        :param statement: SQL statement string
        :param params: tuple or dict of statement parameters
        """
        if isinstance(params, tuple):
            parameters = {}
            if op == Operation.DELETE:
                regexp = '^DELETE FROM (.+?) WHERE'
                match = re.match(regexp, statement)
                tablename = match.groups()[0].strip('"').strip("'").strip('`')
                table = self.metadata.tables[tablename]
                columns = table.primary_key.columns.values()
                for index, column in enumerate(columns):
                    parameters[column.name] = params[index]
            else:
                columns = [
                    column.strip() for column in
                    statement.split('(')[1].split(')')[0].split(',')
                ]
                for index, column in enumerate(columns):
                    parameters[column] = params[index]
            return parameters
        return params
