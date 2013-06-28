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


class GeneratedIdentity():
    pass


def identity(obj):
    id_ = []
    for attr in obj._sa_class_manager.values():
        prop = attr.property
        if isinstance(prop, sa.orm.ColumnProperty):
            column = prop.columns[0]
            if column.primary_key:
                value = getattr(obj, column.name)
                if value is None and column.autoincrement:
                    id_.append(GeneratedIdentity())
                else:
                    id_.append(getattr(obj, column.name))
    return tuple(id_)


def tracked_operation(func):
    @wraps(func)
    def wrapper(self, mapper, connection, target):
        if not self.manager.options['versioning']:
            return
        if not is_versioned(target):
            return

        key = (target.__class__, identity(target))

        return func(self, key, target)
    return wrapper


class UnitOfWork(object):
    def __init__(self, manager):
        self.manager = manager
        self.reset()

    def reset(self):
        self.current_transaction = None
        self.operations = OrderedDict()
        self._committing = False
        self.tx_context = {}

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

    def create_version_objects(self, session, flush_context):
        if not self.manager.options['versioning']:
            return

        if self._committing:
            uow = self.preprocess_operations()
            for key, value in uow.items():
                if not session.is_modified(
                    value['target'], include_collections=False
                ) and value['target'] not in session.deleted:
                    continue
                version_obj = value['target'].__versioned__['class']()
                session.add(version_obj)

                version_obj.operation_type = value['operation_type']
                self.assign_attributes(value['target'], version_obj)

                version_obj.transaction_id = (
                    self.current_transaction.id
                )

    def create_transaction_log_entry(self, session):
        if not self.manager.options['versioning']:
            return
        transaction_log_cls = None
        for obj in versioned_objects(session):
            transaction_log_cls = obj.__versioned__['transaction_log']
            break

        if self.current_transaction:
            return self.current_transaction

        if transaction_log_cls:
            if 'meta' in self.tx_context and self.tx_context['meta']:
                for key, value in self.tx_context['meta'].items():
                    if callable(value):
                        self.tx_context['meta'][key] = str(value())

            self.current_transaction = transaction_log_cls(
                issued_at=sa.func.now(),
                **self.tx_context
            )
            session.add(self.current_transaction)
            return self.current_transaction

    def create_transaction_changes_entries(self, session, flush_context):
        if not self.manager.options['versioning']:
            return

        if not self._committing:
            return

        changed_entities = set()

        for key in self.operations:
            changed_entities.add(key[0])

        for entity in changed_entities:
            session.execute(
                '''INSERT INTO transaction_changes
                (transaction_id, entity_name)
                VALUES (:transaction_id, :entity_name)''',
                {
                    'transaction_id': self.current_transaction.id,
                    'entity_name': entity.__name__
                }
            )

        self.operations = OrderedDict()
        self._committing = False

    def before_commit(self, session):
        self._committing = True

    def clear_transaction(self, session):
        self.current_transaction = None
        self.operations = OrderedDict()
        self._committing = False

    def version_association_table_record(self, conn, table_name, params, op):
        params['operation_type'] = op
        params['transaction_id'] = self.current_transaction.id
        stmt = (
            self.manager.metadata.tables[table_name + '_history']
            .insert()
            .values(**params)
        )
        conn.execute(stmt)

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
                        and key != 'revision'):
                    value = None
                else:
                    value = getattr(parent_obj, key)
                setattr(version_obj, key, value)

    def preprocess_operations(self):
        uow = self.operations.items()
        uow_copy = OrderedDict()
        for id_, operation in uow:
            processed_id = tuple([
                id_[0],
                identity(operation['target'])
            ])
            uow_copy[processed_id] = operation
        return uow_copy
