from collections import OrderedDict
from functools import wraps
import itertools
import sqlalchemy as sa
from .operation import Operation


def versioned_objects(session):
    iterator = itertools.chain(session.new, session.dirty, session.deleted)

    return [
        obj for obj in iterator
        if is_versioned(obj)
    ]


def is_versioned(obj):
    return (
        hasattr(obj, '__versioned__') and
        (
            (
                'versioning' in obj.__versioned__ and
                obj.__versioned__['versioning']
            ) or
            'versioning' not in obj.__versioned__
        )
    )


def identity(obj):
    """
    Return the identity of given sqlalchemy declarative model instance as a
    tuple.

    :param obj: sqlalchemy declarative model instance
    """
    id_ = []
    for attr in obj._sa_class_manager.values():
        prop = attr.property
        if isinstance(prop, sa.orm.ColumnProperty):
            column = prop.columns[0]
            if column.primary_key:
                id_.append(getattr(obj, column.name))
    return tuple(id_)


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

        :param session: session to track the operations from
        """
        sa.event.listen(
            session, 'after_flush', self.after_flush
        )
        sa.event.listen(
            session, 'before_commit', self.before_commit
        )
        sa.event.listen(
            session, 'after_commit', self.clear_transaction
        )
        sa.event.listen(
            session, 'after_rollback', self.clear_transaction
        )

    @tracked_operation
    def track_inserts(self, key, target):
        if key in self.operations:
            self.operations[key]['target'] = target
            self.operations[key]['operation_type'] = Operation.UPDATE
        else:
            self.operations[key] = {
                'target': target,
                'operation_type': Operation.INSERT
            }

    @tracked_operation
    def track_updates(self, key, target):
        self.operations[key] = {
            'target': target,
            'operation_type': Operation.UPDATE
        }

    @tracked_operation
    def track_deletes(self, key, target):
        self.operations[key] = {
            'target': target,
            'operation_type': Operation.DELETE
        }

    def create_version_objects(self, session):
        if not self.manager.options['versioning']:
            return

        if self._committing:
            for key, value in self.operations.items():
                if not session.is_modified(
                    value['target'], include_collections=False
                ) and value['target'] not in session.deleted:
                    continue
                version_obj = value['target'].__versioned__['class']()
                session.add(version_obj)

                version_obj.operation_type = value['operation_type']
                self.assign_attributes(value['target'], version_obj)

                version_obj.transaction_id = (
                    self.current_transaction_id
                )

    def create_association_versions(self, session):
        for stmt in self.pending_statements:
            stmt = stmt.values(transaction_id=self.current_transaction_id)
            session.execute(stmt)

    def after_flush(self, session, flush_context):
        if not self.manager.options['versioning']:
            return

        if self._committing:
            self.create_transaction_log_entry(session)
            self.create_version_objects(session)
            self.create_association_versions(session)
            self.create_transaction_changes_entries(session)

            self.operations = OrderedDict()
            self._committing = False

    def create_transaction_log_entry(self, session):
        if self.current_transaction_id:
            return self.current_transaction_id

        if (
            self.manager.transaction_log_cls and
            (
                self.changed_entities(session) or
                self.pending_statements
            )
        ):
            if 'meta' in self.tx_context and self.tx_context['meta']:
                for key, value in self.tx_context['meta'].items():
                    if callable(value):
                        self.tx_context['meta'][key] = str(value())

            table = self.manager.transaction_log_cls.__table__

            stmt = (
                table
                .insert()
                .returning(table.c.id)
                .values(
                    issued_at=sa.func.now(),
                    **self.tx_context
                )
            )
            self.current_transaction_id = session.execute(stmt).fetchone()[0]
            return self.current_transaction_id

    def changed_entities(self, session):
        changed_entities = set()

        for key, value in self.operations.items():
            if not session.is_modified(
                value['target'], include_collections=False
            ) and value['target'] not in session.deleted:
                continue
            changed_entities.add(key[0])
        return changed_entities

    def create_transaction_changes_entries(self, session):
        for entity in self.changed_entities(session):
            changes = self.manager.transaction_changes_cls(
                transaction_id=self.current_transaction_id,
                entity_name=unicode(entity.__name__)
            )
            session.add(changes)

    def before_commit(self, session):
        """
        Before commit listener that marks the internal state of this
        UnitOfWork as committing.

        :param session: SQLAlchemy session object
        """
        self._committing = True

    def clear_transaction(self, session):
        self.current_transaction_id = None
        self.operations = OrderedDict()
        self._committing = False
        self.pending_statements = []

    def version_association_table_record(self, conn, table_name, params, op):
        params['operation_type'] = op
        stmt = (
            self.manager.metadata.tables[table_name + '_history']
            .insert()
            .values(params)
        )
        self.pending_statements.append(stmt)

    def version_association_table_records(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        if not self.manager.options['versioning']:
            return

        op = None

        if statement.startswith('INSERT INTO '):
            op = Operation.INSERT
        elif statement.startswith('DELETE FROM '):
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
                        self.version_association_table_record(
                            conn, table_name, params, op
                        )
                else:
                    self.version_association_table_record(
                        conn, table_name, parameters, op
                    )

    def assign_attributes(self, parent_obj, version_obj):
        excluded_attributes = self.manager.option(parent_obj, 'exclude')
        for key, attr in parent_obj._sa_class_manager.items():
            if key in excluded_attributes:
                continue
            if isinstance(attr.property, sa.orm.ColumnProperty):
                if (version_obj.operation_type == Operation.DELETE and
                        attr.property.columns[0].primary_key is not True
                        and key != 'transaction_id'):
                    value = None
                else:
                    value = getattr(parent_obj, key)
                setattr(version_obj, key, value)
