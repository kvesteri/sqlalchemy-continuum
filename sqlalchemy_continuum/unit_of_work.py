from copy import copy
import re
from functools import wraps
import sqlalchemy as sa
from sqlalchemy_utils.functions import has_changes
from sqlalchemy_utils import identity
from .operation import Operation, Operations
from .utils import (
    is_versioned,
    is_modified,
    tx_column_name,
    end_tx_column_name,
    versioned_column_properties
)


def tracked_operation(func):
    @wraps(func)
    def wrapper(self, mapper, connection, target):
        if not self.manager.options['versioning']:
            return
        if not is_versioned(target):
            return
        return func(self, target)
    return wrapper


class UnitOfWork(object):
    def __init__(self, manager):
        self.manager = manager
        self.reset()

    def reset(self):
        """
        Reset the internal state of this UnitOfWork object. Normally this is
        called after transaction has been committed or rolled back.
        """
        self.history_session = None
        self.current_transaction = None
        self.operations = Operations()
        self.tx_context = {}
        self.tx_meta = {}
        self.pending_statements = []
        self.version_objs = {}

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
    def track_inserts(self, target):
        """
        Track object insert operations. Whenever object is inserted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        if not is_modified(target):
            return
        self.operations.add_insert(target)

    @tracked_operation
    def track_updates(self, target):
        """
        Track object update operations. Whenever object is updated it is
        added to this UnitOfWork's internal operations dictionary.
        """
        if not is_modified(target):
            return
        self.operations.add_update(target)

    @tracked_operation
    def track_deletes(self, target):
        """
        Track object deletion operations. Whenever object is deleted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        self.operations.add_delete(target)

    def before_flush(self, session, flush_context, instances):
        if not self.manager.options['versioning']:
            return

        if session == self.history_session:
            return

        if not self.current_transaction:
            self.history_session = sa.orm.session.Session(
                bind=session.connection()
            )
            self.current_transaction = self.manager.transaction_log_cls(
                **self.tx_context
            )
            session.add(self.current_transaction)

    def after_flush(self, session, flush_context):
        if not self.manager.options['versioning']:
            return

        if session == self.history_session:
            return

        self.make_history(session)

    def clear(self, session):
        """
        Simple SQLAlchemy listener that is being invoked after succesful
        transaction commit or when transaction rollback occurs. The purpose of
        this listener is to reset this UnitOfWork back to its initialization
        state.

        :param session: SQLAlchemy session object
        """
        self.reset()

    def create_history_objects(self, session):
        """
        Create history objects for given session based on operations collected
        by insert, update and deleted trackers.

        :param session: SQLAlchemy session object
        """
        if not self.manager.options['versioning']:
            return

        for key, operation in copy(self.operations).items():
            if operation.processed:
                continue
            target = operation.target

            if not self.current_transaction:
                raise Exception(
                    'Current transaction not available.'
                )

            version_cls = target.__versioned__['class']
            tx_column = self.manager.option(
                target,
                'transaction_column_name'
            )

            version_id = identity(target) + (self.current_transaction.id, )

            version_key = (version_cls, version_id)
            if version_key not in self.version_objs:
                version_obj = version_cls()
                self.version_objs[version_key] = version_obj
                self.history_session.add(version_obj)
            else:
                version_obj = self.version_objs[version_key]

            version_obj.operation_type = operation.type

            if not getattr(version_obj, tx_column):
                setattr(
                    version_obj,
                    tx_column,
                    self.current_transaction.id
                )

            self.assign_attributes(target, version_obj)

            operation.processed = True

            self.update_version_validity(
                target,
                version_obj
            )

        self.history_session.flush()

    def version_validity_subquery(self, parent, version_obj):
        """
        Return the subquery needed by update_version_validity.

        This method is only used when using 'validity' versioning strategy.

        :param parent: SQLAlchemy declarative parent object
        :parem version_obj: SQLAlchemy declarative version object
        """
        fetcher = self.manager.fetcher(parent)
        session = sa.orm.object_session(version_obj)

        subquery = fetcher._transaction_id_subquery(
            version_obj, next_or_prev='prev'
        )
        if session.connection().engine.dialect.name == 'mysql':
            return sa.select(
                ['max_1'],
                from_obj=[
                    sa.sql.expression.alias(subquery, name='subquery')
                ]
            )
        return subquery

    def update_version_validity(self, parent, version_obj):
        """
        Updates previous version object end_transaction_id based on given
        parent object and newly created version object.

        This method is only used when using 'validity' versioning strategy.

        :param parent: SQLAlchemy declarative parent object
        :parem version_obj: SQLAlchemy declarative version object
        """
        if (
            self.manager.option(parent, 'strategy') ==
            'validity'
        ):
            fetcher = self.manager.fetcher(parent)
            session = sa.orm.object_session(version_obj)

            subquery = self.version_validity_subquery(parent, version_obj)
            query = (
                session.query(version_obj.__class__)
                .filter(
                    sa.and_(
                        getattr(
                            version_obj.__class__,
                            tx_column_name(version_obj)
                        ) == subquery,
                        *fetcher.parent_identity_correlation(version_obj)
                    )
                )
            )
            query.update(
                {
                    end_tx_column_name(version_obj):
                    self.current_transaction.id
                },
                synchronize_session=False
            )

    def create_association_versions(self, session):
        """
        Creates association table history records for given session.

        :param session: SQLAlchemy session object
        """
        statements = copy(self.pending_statements)
        for stmt in statements:
            stmt = stmt.values(transaction_id=self.current_transaction.id)
            session.execute(stmt)
        self.pending_statements = []

    def make_history(self, session):
        """
        Create transaction, transaction changes records, history objects.

        :param session: SQLAlchemy session object
        """
        if not self.manager.options['versioning']:
            return

        if self.current_transaction.id:
            self.create_association_versions(session)
            for plugin in self.manager.plugins:
                plugin.before_flush(self, session)

        self.create_history_objects(session)

    @property
    def has_changes(self):
        """
        Return whether or not transaction entry should be created for given
        SQLAlchemy session object.

        :param session: SQLAlchemy session
        """
        return self.operations or self.pending_statements

    def append_association_operation(self, conn, table_name, params, op):
        """
        Append history association operation to pending_statements list.
        """
        params['operation_type'] = op
        stmt = (
            self.manager.metadata.tables[table_name + '_history']
            .insert()
            .values(params)
        )
        self.pending_statements.append(stmt)

    def track_association_operations(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        """
        Track association operations and adds the generated history
        association operations to pending_statements list.
        """
        if not self.manager.options['versioning']:
            return

        op = None

        if context.isinsert:
            op = Operation.INSERT
        elif context.isdelete:
            op = Operation.DELETE

        if op is not None:
            table_name = statement.split(' ')[2]
            table_names = [
                table.name for table in self.manager.association_tables
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
                table = self.manager.metadata.tables[tablename]
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

    def should_nullify_column(self, version_obj, prop):
        """
        Return whether or not given column of given version object should
        be nullified (set to None) at the end of the transaction.

        :param version_obj:
            Version object to check the attribute nullification
        :paremt attr:
            SQLAlchemy ColumnProperty object
        """
        parent = version_obj.__parent_class__
        return (
            not self.manager.option(parent, 'store_data_at_delete') and
            version_obj.operation_type == Operation.DELETE and
            not prop.columns[0].primary_key and
            prop.key !=
            self.manager.option(
                parent,
                'transaction_column_name'
            )
        )

    def assign_attributes(self, parent_obj, version_obj):
        """
        Assign attributes values from parent object to version object. If the
        parent object is deleted this method assigns None values to all version
        object's attributes.

        :param parent_obj:
            Parent object to get the attribute values from
        :param version_obj:
            Version object to assign the attribute values to
        """
        excluded_attributes = self.manager.option(parent_obj, 'exclude')
        for prop in versioned_column_properties(parent_obj):
            if prop.key in excluded_attributes:
                continue
            if self.should_nullify_column(version_obj, prop):
                value = None
            else:
                value = getattr(parent_obj, prop.key)
                self.assign_modified_flag(
                    parent_obj, version_obj, prop.key
                )

            setattr(version_obj, prop.key, value)

    def assign_modified_flag(self, parent_obj, version_obj, attr_name):
        """
        Assign modified flag for given attribute of given version model object
        based on the modification state of this property in given parent model
        object.

        :param parent_obj:
            Parent object to check the modification state of given attribute
        :param version_obj:
            Version object to assign the modification flag into
        :param attr_name:
            Name of the attribute to check the modification state
        """
        if (
            self.manager.option(parent_obj, 'track_property_modifications')
            and
            has_changes(parent_obj, attr_name)
        ):
            setattr(
                version_obj,
                attr_name + self.manager.option(
                    parent_obj,
                    'modified_flag_suffix'
                ),
                True
            )
