import re
from functools import wraps
from inflection import underscore, pluralize

import sqlalchemy as sa
from sqlalchemy.orm import object_session
from sqlalchemy_utils.functions import is_auto_assigned_date_column
from sqlalchemy_utils.types import TSVectorType
from .builder import Builder
from .fetcher import SubqueryFetcher, ValidityFetcher
from .operation import Operation
from .plugins import PluginCollection
from .transaction_log import TransactionLogFactory
from .unit_of_work import UnitOfWork
from .utils import is_modified, is_versioned


def tracked_operation(func):
    @wraps(func)
    def wrapper(self, mapper, connection, target):
        if not is_versioned(target):
            return
        session = object_session(target)
        conn = session.connection()
        uow = self.units_of_work[conn]
        return func(self, uow, target)
    return wrapper


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
        self.uow_class = unit_of_work_cls
        if builder is None:
            self.builder = Builder()
        else:
            self.builder = builder
        self.builder.manager = self

        self.reset()
        self.options = {
            'versioning': True,
            'base_classes': None,
            'table_name': '%s_version',
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

        # A dictionary of units of work. Keys as connection objects and values
        # as UnitOfWork objects.
        self.units_of_work = {}

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
        self.association_version_tables = set([])
        self.declarative_base = None
        self.transaction_log_cls = None
        self.version_class_map = {}
        self.parent_class_map = {}

        self.metadata = None

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

    def track_operations(self, mapper):
        """
        Attach listeners for specified mapper that track SQL inserts, updates
        and deletes.

        :param mapper: mapper to track the SQL operations from
        """
        sa.event.listen(
            mapper, 'after_delete', self.track_deletes
        )
        sa.event.listen(
            mapper, 'after_update', self.track_updates
        )
        sa.event.listen(
            mapper, 'after_insert', self.track_inserts
        )

    def track_session(self, session):
        """
        Attach listeners that track the operations (flushing, committing and
        rolling back) of given session. This method should be used in
        conjuction with `track_operations`.

        :param session: SQLAlchemy session to track the operations from
        """
        sa.event.listen(
            session, 'before_flush', self.before_flush
        )
        sa.event.listen(
            session, 'after_flush', self.after_flush
        )
        sa.event.listen(
            session, 'after_commit', self.clear
        )
        sa.event.listen(
            session, 'after_rollback', self.clear
        )

    @tracked_operation
    def track_inserts(self, uow, target):
        """
        Track object insert operations. Whenever object is inserted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        if not is_modified(target):
            return
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

    def unit_of_work(self, obj):
        """
        Return the associated SQLAlchemy-Continuum UnitOfWork object for given
        SQLAlchemy connection or session or declarative model object.

        If no UnitOfWork object exists for given object then this method tries
        to create one.

        :param obj:
            Either a SQLAlchemy declarative model object or SQLAlchemy
            connection object or SQLAlchemy session object
        """
        from sqlalchemy.orm.exc import UnmappedInstanceError

        if hasattr(obj, 'bind'):
            conn = obj.bind
        else:
            try:
                conn = object_session(obj).bind
            except UnmappedInstanceError:
                conn = obj

        if not isinstance(conn, sa.engine.base.Connection):
            raise TypeError(
                'This method accepts only Session, Connection and declarative '
                'model objects.'
            )

        if conn in self.units_of_work:
            return self.units_of_work[conn]
        else:
            uow = self.uow_class(self)
            self.units_of_work[conn] = uow
            return uow

    def before_flush(self, session, flush_context, instances):
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
        conn = session.bind
        uow = self.units_of_work[conn]
        uow.reset()

    def append_association_operation(self, conn, table_name, params, op):
        """
        Append history association operation to pending_statements list.
        """
        params['operation_type'] = op
        stmt = (
            self.metadata.tables[self.options['table_name'] % table_name]
            .insert()
            .values(params)
        )
        uow = self.units_of_work[conn]
        uow.pending_statements.append(stmt)

    def track_association_operations(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        """
        Track association operations and adds the generated history
        association operations to pending_statements list.
        """
        if not self.options['versioning']:
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
