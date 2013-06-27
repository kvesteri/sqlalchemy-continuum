from collections import OrderedDict
from contextlib import contextmanager
import itertools
from inflection import underscore, pluralize
from copy import copy
import sqlalchemy as sa
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import HSTORE
from .model_builder import VersionedModelBuilder
from .table_builder import VersionedTableBuilder
from .relationship_builder import VersionedRelationshipBuilder
from .drivers.postgresql import PostgreSQLAdapter
from .operation import Operation


def versioned_objects(session):
    iterator = itertools.chain(session.new, session.dirty, session.deleted)

    return [
        obj for obj in iterator
        if hasattr(obj, '__versioned__') and
        (
            (
                'versioning' in obj.__versioned__ and
                obj.__versioned__['versioning']
            ) or
            'versioning' not in obj.__versioned__
        )
    ]


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


class VersionCreator(object):
    def __init__(self, manager):
        self.manager = manager

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

    def preprocess_unit_of_work(self):
        uow = self.manager.unit_of_work.items()
        uow_copy = OrderedDict()
        for id_, operation in uow:
            processed_id = tuple([
                id_[0],
                identity(operation['target'])
            ])
            uow_copy[processed_id] = operation
        return uow_copy

    def create_version_objects(self, session):
        uow = self.preprocess_unit_of_work()
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
                self.manager._current_transaction_obj.id
            )


class VersioningManager(object):
    def __init__(
        self,
        version_creator_cls=VersionCreator
    ):
        self.reset(version_creator_cls)

    def reset(self, version_creator_cls=VersionCreator):
        """
        This method should be used in test cases that create models on the fly.
        Otherwise history_class_map and some other variables would be polluted
        by no more used model classes.
        """
        self.tables = {}
        self.pending_classes = []
        self.association_tables = set([])
        self.association_history_tables = set([])
        self.history_class_map = {}
        self._tx_context = {}
        self._current_transaction_obj = None
        self._committing = False
        self.unit_of_work = OrderedDict()
        self.added_entities = []

        self.metadata = None
        self.version_creator = version_creator_cls(self)
        self.options = {
            'versioning': True,
            'base_classes': None,
            'table_name': '%s_history',
            'exclude': [],
            'revision_column_name': 'revision',
            'transaction_column_name': 'transaction_id',
            'operation_type_column_name': 'operation_type',
            'relation_naming_function': lambda a: pluralize(underscore(a))
        }

    @contextmanager
    def tx_context(self, **tx_context):
        old_tx_context = self._tx_context
        self._tx_context = tx_context
        yield
        self._tx_context = old_tx_context

    def declarative_base(self, model):
        for parent in model.__bases__:
            try:
                parent.metadata
                return self.declarative_base(parent)
            except AttributeError:
                pass
        return model

    def transaction_log_base_factory(self, cls):
        base = self.declarative_base(cls)
        naming_func = self.options['relation_naming_function']

        class TransactionLogBase(base):
            __abstract__ = True
            id = sa.Column(sa.BigInteger, primary_key=True)
            issued_at = sa.Column(sa.DateTime)
            meta = sa.Column(MutableDict.as_mutable(HSTORE))

            @property
            def entity_names(obj_self):
                return [changes.entity_name for changes in obj_self.changes]

            @property
            def changed_entities(obj_self):
                tuples = set(self.history_class_map.items())
                entities = []

                for class_, history_class in tuples:
                    if class_.__name__ not in obj_self.entity_names:
                        continue

                    try:
                        value = getattr(
                            obj_self,
                            naming_func(class_.__name__)
                        )
                    except AttributeError:
                        continue

                    if value:
                        entities.append((
                            history_class,
                            value
                        ))
                return dict(entities)

        return TransactionLogBase

    def transaction_log_factory(self, cls):
        class TransactionLog(self.transaction_log_base_factory(cls)):
            __tablename__ = 'transaction_log'

        return TransactionLog

    def create_transaction_log(self, cls):
        if 'TransactionLog' not in cls._decl_class_registry:
            return self.transaction_log_factory(cls)
        return cls._decl_class_registry['TransactionLog']

    def create_transaction_changes(self, cls, transaction_log_class):
        base = self.declarative_base(cls)

        if 'TransactionChanges' not in cls._decl_class_registry:
            class TransactionChanges(base):
                __tablename__ = 'transaction_changes'
                transaction_id = sa.Column(
                    sa.BigInteger,
                    autoincrement=True,
                    primary_key=True
                )
                entity_name = sa.Column(sa.Unicode(255), primary_key=True)

                transaction_log = sa.orm.relationship(
                    transaction_log_class,
                    backref=sa.orm.backref(
                        'changes'
                    ),
                    primaryjoin=transaction_log_class.id == transaction_id,
                    foreign_keys=[transaction_id]
                )

            return TransactionChanges
        return cls._decl_class_registry['TransactionChanges']

    def build_tables(self):
        for cls in self.pending_classes:
            if not self.option(cls, 'versioning'):
                continue

            inherited_table = None
            for class_ in self.tables:
                if (issubclass(cls, class_) and
                        cls.__table__ == class_.__table__):
                    inherited_table = self.tables[class_]
                    break

            builder = VersionedTableBuilder(
                self,
                cls.__table__,
                model=cls
            )
            if inherited_table is not None:
                self.tables[class_] = builder.build_table(inherited_table)
            else:
                table = builder.build_table()
                self.tables[cls] = table

    def build_triggers(self):
        if self.pending_classes:
            adapter = PostgreSQLAdapter()
            adapter.build_triggers(self.pending_classes)

    def build_models(self):
        if self.pending_classes:
            cls = self.pending_classes[0]
            TransactionLog = self.create_transaction_log(cls)
            TransactionChanges = self.create_transaction_changes(
                cls, TransactionLog
            )

            for cls in self.pending_classes:
                if not self.option(cls, 'versioning'):
                    continue

                if cls in self.tables:
                    builder = VersionedModelBuilder(self, cls)
                    builder(
                        self.tables[cls],
                        TransactionLog,
                        TransactionChanges
                    )

    def build_relationships(self, history_classes):
        # Build relationships for all history classes.
        for cls in history_classes:
            if not self.option(cls, 'versioning'):
                continue
            builder = VersionedRelationshipBuilder(self, cls)
            builder.build_reflected_relationships()

    def option(self, model, name):
        try:
            return model.__versioned__[name]
        except (AttributeError, KeyError):
            return self.options[name]

    def instrument_versioned_classes(self, mapper, cls):
        if not self.options['versioning']:
            return

        if hasattr(cls, '__versioned__'):
            if (not cls.__versioned__.get('class')
                    and cls not in self.pending_classes):
                self.pending_classes.append(cls)
                self.metadata = cls.metadata

    def configure_versioned_classes(self):
        if not self.options['versioning']:
            return

        self.build_tables()
        self.build_models()
        #self.build_triggers()

        # Create copy of all pending versioned classes so that we can inspect
        # them later when creating relationships.
        pending_copy = copy(self.pending_classes)
        self.pending_classes = []
        self.build_relationships(pending_copy)

        for cls in pending_copy:
            # set the "active_history" flag
            for prop in cls.__mapper__.iterate_properties:
                getattr(cls, prop.key).impl.active_history = True

    def assign_revisions(self, session):
        if not self.options['versioning']:
            return
        for obj in versioned_objects(session):
            if (session.is_modified(obj, include_collections=False) or
                    obj in session.deleted):
                if not obj.revision:
                    obj.revision = 1
                else:
                    obj.revision += 1

    def track_inserts(self, mapper, connection, target):
        if not self.options['versioning']:
            return
        if not hasattr(target, '__versioned__'):
            return
        key = (target.__class__, identity(target))
        if key in self.unit_of_work:
            self.unit_of_work[key]['target'] = target
            self.unit_of_work[key]['operation_type'] = Operation.UPDATE
        else:
            self.unit_of_work[key] = {
                'target': target,
                'operation_type': Operation.INSERT
            }

    def track_updates(self, mapper, connection, target):
        if not self.options['versioning']:
            return
        if not hasattr(target, '__versioned__'):
            return
        key = (target.__class__, identity(target))
        self.unit_of_work[key] = {
            'target': target,
            'operation_type': Operation.UPDATE
        }

    def track_deletes(self, mapper, connection, target):
        if not self.options['versioning']:
            return
        if not hasattr(target, '__versioned__'):
            return

        key = (target.__class__, identity(target))
        self.unit_of_work[key] = {
            'target': target,
            'operation_type': Operation.DELETE
        }

    def create_version_objects(self, session, flush_context):
        if not self.options['versioning']:
            return

        if self._committing:
            self.version_creator.create_version_objects(session)

    def create_transaction_log_entry(self, session):
        if not self.options['versioning']:
            return
        transaction_log_cls = None
        for obj in versioned_objects(session):
            transaction_log_cls = obj.__versioned__['transaction_log']
            break

        if self._current_transaction_obj:
            return self._current_transaction_obj

        if transaction_log_cls:
            if 'meta' in self._tx_context and self._tx_context['meta']:
                for key, value in self._tx_context['meta'].items():
                    if callable(value):
                        self._tx_context['meta'][key] = str(value())

            self._current_transaction_obj = transaction_log_cls(
                issued_at=sa.func.now(),
                **self._tx_context
            )
            session.add(self._current_transaction_obj)
            return self._current_transaction_obj

    def create_transaction_changes_entries(self, session, flush_context):
        if not self.options['versioning']:
            return

        if not self._committing:
            return

        changed_entities = set([])
        for key in self.unit_of_work:
            changed_entities.add(key[0])
        for entity in changed_entities:
            session.execute(
                '''INSERT INTO transaction_changes
                (transaction_id, entity_name)
                VALUES (:transaction_id, :entity_name)''',
                {
                    'transaction_id': self._current_transaction_obj.id,
                    'entity_name': entity.__name__
                }
            )

        self.unit_of_work = OrderedDict()
        self._committing = False

    def before_commit(self, session):
        self._committing = True

    def clear_transaction(self, session):
        self._current_transaction_obj = None
        self.added_entities = []
        self.unit_of_work = OrderedDict()
        self._committing = False

    def version_association_table_record(self, conn, table_name, params, op):
        params['operation_type'] = op
        params['transaction_id'] = self._current_transaction_obj.id
        stmt = (
            self.metadata.tables[table_name + '_history']
            .insert()
            .values(**params)
        )
        conn.execute(stmt)

    def version_association_table_records(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        if not self.options['versioning']:
            return

        op = None

        if 'INSERT INTO ' == statement[0:12]:
            op = Operation.INSERT
        elif 'DELETE FROM ' == statement[0:12]:
            op = Operation.DELETE

        if op is not None:
            table_name = statement.split(' ')[2]
            table_names = [table.name for table in self.association_tables]
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
