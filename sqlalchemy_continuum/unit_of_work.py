import re
from collections import OrderedDict
from functools import wraps
import sqlalchemy as sa
from sqlalchemy_utils.functions import identity
from .operation import Operation
from .strategy import VersioningStrategy
from .utils import is_versioned, is_modified, has_changes


def tracked_operation(func):
    @wraps(func)
    def wrapper(self, mapper, connection, target):
        if not self.manager.options['versioning']:
            return
        if not is_versioned(target):
            return
        # we cannot use target._sa_instance_state.identity here since object's
        # is not yet updated at this phase
        key = (target.__class__, identity(target))

        return func(self, key, target)
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
        self.current_transaction_id = None
        self.operations = OrderedDict()
        self._committing = False
        self.tx_context = {}
        self.tx_meta = {}
        self.pending_statements = []

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
            session, 'after_flush', self.after_flush
        )
        sa.event.listen(
            session, 'before_commit', self.before_commit
        )
        sa.event.listen(
            session, 'after_commit', self.clear
        )
        sa.event.listen(
            session, 'after_rollback', self.clear
        )

    @tracked_operation
    def track_inserts(self, key, target):
        """
        Tracks object insert operations. Whenever object is inserted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        if key in self.operations:
            # If the object is deleted and then inserted within the same
            # transaction we are actually dealing with an update.
            self.operations[key]['target'] = target
            self.operations[key]['operation_type'] = Operation.UPDATE
        else:
            self.operations[key] = {
                'target': target,
                'operation_type': Operation.INSERT
            }

    @tracked_operation
    def track_updates(self, key, target):
        """
        Tracks object update operations. Whenever object is updated it is
        added to this UnitOfWork's internal operations dictionary.
        """
        self.operations[key] = {
            'target': target,
            'operation_type': Operation.UPDATE
        }

    @tracked_operation
    def track_deletes(self, key, target):
        """
        Tracks object deletion operations. Whenever object is deleted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        self.operations[key] = {
            'target': target,
            'operation_type': Operation.DELETE
        }

    def create_history_objects(self, session):
        """
        Create history objects for given session based on operations collected
        by insert, update and deleted trackers.

        :param session: SQLAlchemy session object
        """
        if not self.manager.options['versioning']:
            return

        for key, value in self.operations.items():
            if (
                not is_modified(value['target']) and
                value['target'] not in session.deleted
            ):
                continue
            version_obj = value['target'].__versioned__['class']()
            session.add(version_obj)

            version_obj.operation_type = value['operation_type']
            self.assign_attributes(value['target'], version_obj)

            version_obj.transaction_id = (
                self.current_transaction_id
            )
            self.update_version_validity(value['target'], version_obj)

    def update_version_validity(self, parent, version_obj):
        if (
            self.manager.option(parent, 'strategy') ==
            VersioningStrategy.VALIDITY
        ):
            fetcher = self.manager.fetcher
            session = sa.orm.object_session(version_obj)
            return (
                session.query(version_obj.__class__)
                .filter(
                    sa.and_(
                        version_obj.__class__.transaction_id ==
                        fetcher._transaction_id_subquery(
                            version_obj, next_or_prev='prev'
                        ),
                        *fetcher._pk_correlation_condition(version_obj)
                    )
                )
                .update(
                    {'end_transaction_id': self.current_transaction_id},
                    synchronize_session=False
                )
            )

    def create_association_versions(self, session):
        """
        Creates association table history records for given session.

        :param session: SQLAlchemy session object
        """
        for stmt in self.pending_statements:
            stmt = stmt.values(transaction_id=self.current_transaction_id)
            session.execute(stmt)

    def after_flush(self, session, flush_context):
        """
        SQLAlchemy after_flush event listener that handles all the logic for
        creating necessary TransactionLog, TransactionChanges and History
        objects.

        :param session: SQLAlchemy session object
        :param flush_context: flush_context dictionary
        """
        if not self.manager.options['versioning']:
            return

        if self._committing:
            self.create_transaction_log_entry(session)
            self.create_history_objects(session)
            self.create_association_versions(session)
            self.create_transaction_changes_entries(session)
            self.create_transaction_meta_entries(session)

            self.operations = OrderedDict()
            self._committing = False

    def create_transaction_log_entry(self, session):
        """
        Creates TransactionLog object for current transaction. We use raw
        insert here to be able to get current transaction id.

        :param session: SQLAlchemy session
        """
        if self.current_transaction_id:
            return self.current_transaction_id

        if (
            self.manager.transaction_log_cls and
            (
                self.changed_entities(session) or
                self.pending_statements
            )
        ):
            table = self.manager.transaction_log_cls.__table__

            stmt = (
                table
                .insert()
                .values(
                    issued_at=sa.func.now(),
                    **self.tx_context
                )
            )
            if session.connection().engine.driver == 'psycopg2':
                stmt = stmt.returning(table.c.id)
                self.current_transaction_id = (
                    session.execute(stmt).fetchone()[0]
                )
            else:
                self.current_transaction_id = session.execute(stmt).lastrowid
            return self.current_transaction_id

    def changed_entities(self, session):
        """
        Return a set of changed versioned entities for given session.

        :param session: SQLAlchemy session object
        """
        changed_entities = set()

        for key, value in self.operations.iteritems():
            if (
                not is_modified(value['target']) and
                value['target'] not in session.deleted
            ):
                continue
            changed_entities.add(key[0])
        return changed_entities

    def create_transaction_changes_entries(self, session):
        """
        Create transaction changes entries based on all operations that
        occurred during this UnitOfWork. For each entity that has been affected
        by an operation during this UnitOfWork this method creates a new
        TransactionChanges object.

        :param session: SQLAlchemy session object
        """
        for entity in self.changed_entities(session):
            changes = self.manager.transaction_changes_cls(
                transaction_id=self.current_transaction_id,
                entity_name=unicode(entity.__name__)
            )
            session.add(changes)

    def create_transaction_meta_entries(self, session):
        """
        Create transaction meta entries based on transaction meta context
        key-value pairs.

        :param session: SQLAlchemy session object
        """
        if (
            self.tx_meta and
            (
                self.changed_entities(session) or
                self.pending_statements
            )
        ):
            for key, value in self.tx_meta.items():
                if callable(value):
                    value = unicode(value())
                meta = self.manager.transaction_meta_cls(
                    transaction_id=self.current_transaction_id,
                    key=key,
                    value=value
                )
                session.add(meta)

    def before_commit(self, session):
        """
        SQLAlchemy before commit listener that marks the internal state of this
        UnitOfWork as committing. This state is later on used by after_flush
        listener which checks if the session is actually committing or if the
        flush occurs before session commit.

        :param session: SQLAlchemy session object
        """
        self._committing = True

    def clear(self, session):
        """
        Simple SQLAlchemy listener that is being invoked after succesful
        transaction commit or when transaction rollback occurs. The purpose of
        this listener is to reset this UnitOfWork back to its initialization
        state.

        :param session: SQLAlchey session object
        """
        self.reset()

    def append_association_operation(self, conn, table_name, params, op):
        """
        Appends history association operation to pending_statements list.
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
        Tracks association operations and adds the generated history
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

    def assign_attributes(self, parent_obj, version_obj):
        """
        Assigns attributes values from parent object to version object. If the
        parent object is deleted this method assigns None values to all version
        object's attributes.

        :param parent_obj:
            Parent object to get the attribute values from
        :param version_obj:
            Version object to assign the attribute values to
        """
        excluded_attributes = self.manager.option(parent_obj, 'exclude')
        for attr_name, attr in parent_obj._sa_class_manager.items():
            if attr_name in excluded_attributes:
                continue
            if isinstance(attr.property, sa.orm.ColumnProperty):
                if (version_obj.operation_type == Operation.DELETE and
                        attr.property.columns[0].primary_key is not True
                        and attr_name != 'transaction_id'):
                    value = None
                else:
                    value = getattr(parent_obj, attr_name)
                    self.assign_modified_flag(
                        parent_obj, version_obj, attr_name
                    )

                setattr(version_obj, attr_name, value)

    def assign_modified_flag(self, parent_obj, version_obj, attr_name):
        """
        Assigns modified flag for given attribute of given version model object
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
            self.manager.option(
                parent_obj,
                'track_property_modifications'
            ) and
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
