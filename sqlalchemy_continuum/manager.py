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


def versioned_objects(session):
    iterator = itertools.chain(session.new, session.dirty, session.deleted)
    return [obj for obj in iterator if hasattr(obj, '__versioned__')]


class VersioningManager(object):
    strategy = 'orm'
    options = {
        'base_classes': None,
        'table_name': '%s_history',
        'revision_column_name': 'revision',
        'transaction_column_name': 'transaction_id',
        'operation_type_column_name': 'operation_type',
        'relation_naming_function': lambda a: pluralize(underscore(a))
    }

    def __init__(self):
        self.tables = {}
        self.pending_classes = []
        self.association_tables = set([])
        self.association_history_tables = set([])
        self.history_class_map = {}
        self._tx_context = {}
        self.versioning_on = True
        self.metadata = None

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
            def changed_entities(obj_self):
                tuples = set(self.history_class_map.items())
                entities = []

                for class_, history_class in tuples:
                    try:
                        entities.append((
                            history_class,
                            getattr(
                                obj_self,
                                naming_func(class_.__name__)
                            )
                        ))
                    except AttributeError:
                        pass
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
                transaction_id = sa.Column(sa.BigInteger, primary_key=True)
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
            inherited_table = None
            for class_ in self.tables:
                if (issubclass(cls, class_) and
                        cls.__table__ == class_.__table__):
                    inherited_table = self.tables[class_]
                    break

            builder = VersionedTableBuilder(self, cls.__table__)
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
            builder = VersionedRelationshipBuilder(self, cls)
            builder.build_reflected_relationships()

    def instrument_versioned_classes(self, mapper, cls):
        if not self.versioning_on:
            return

        if hasattr(cls, '__versioned__'):
            if (not cls.__versioned__.get('class')
                    and cls not in self.pending_classes):
                self.pending_classes.append(cls)
                self.metadata = cls.metadata

    def configure_versioned_classes(self):
        if not self.versioning_on:
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

    def assign_revisions(self, session, flush_context, instances):
        if not self.versioning_on:
            return
        for obj in versioned_objects(session):
            if (session.is_modified(obj, include_collections=False) or
                    obj in session.deleted):
                if not obj.revision:
                    obj.revision = 1
                else:
                    obj.revision += 1

    def _get_or_create_version_object(self, session, parent_obj):
        history_cls = parent_obj.__versioned__['class']
        for obj in session.new:
            if isinstance(obj, history_cls):
                conditions = [obj.revision == parent_obj.revision]
                for attr in parent_obj._sa_class_manager.values():
                    prop = attr.property
                    if isinstance(prop, sa.orm.ColumnProperty):
                        column = prop.columns[0]
                        if column.primary_key:
                            conditions.append(
                                getattr(obj, column.name) ==
                                getattr(parent_obj, column.name)
                            )
                if all(conditions):
                    return obj
        return history_cls()

    def create_version_objects(self, session, flush_context):
        if not self.versioning_on:
            return
        for obj in versioned_objects(session):

            if not session.is_modified(obj, include_collections=False):
                continue

            version_obj = self._get_or_create_version_object(session, obj)
            if obj in session.new:
                version_obj.operation_type = 0
            elif obj in session.dirty:
                version_obj.operation_type = 1
            elif obj in session.deleted:
                version_obj.operation_type = 2

            for key, attr in obj._sa_class_manager.items():
                if isinstance(attr.property, sa.orm.ColumnProperty):
                    if (version_obj.operation_type == 2 and
                            attr.property.columns[0].primary_key is not True
                            and key != 'revision'):
                        value = None
                    else:
                        value = getattr(obj, key)
                    setattr(version_obj, key, value)

            version_obj.transaction_id = sa.func.txid_current()
            session.add(version_obj)

    def create_transaction_log_entry(self, session):
        if not self.versioning_on:
            return
        transaction_log_cls = None
        for obj in versioned_objects(session):
            transaction_log_cls = obj.__versioned__['transaction_log']
            break
        if transaction_log_cls:
            session.add(
                transaction_log_cls(
                    id=sa.func.txid_current(),
                    issued_at=sa.func.now(),
                    **self._tx_context
                )
            )

    def create_transaction_changes_entries(self, session):
        if not self.versioning_on:
            return
        changed_entities = set([])
        for obj in versioned_objects(session):
            changed_entities.add(obj.__class__)
        for entity in changed_entities:
            session.execute(
                '''INSERT INTO transaction_changes
                (transaction_id, entity_name)
                VALUES (txid_current(), :entity_name)''',
                {'entity_name': entity.__name__}
            )

    def version_association_table_records(
        self, conn, cursor, statement, parameters, context, executemany
    ):

        if 'INSERT INTO ' == statement[0:12]:
            table_name = statement.split(' ')[2]
            table_names = [table.name for table in self.association_tables]
            if table_name in table_names:
                parameters['operation_type'] = 0
                parameters['transaction_id'] = sa.func.txid_current()
                stmt = (
                    self.metadata.tables[table_name + '_history']
                    .insert()
                    .values(**parameters)
                )
                conn.execute(stmt)
        elif 'DELETE FROM ' == statement[0:12]:
            table_name = statement.split(' ')[2]
            table_names = [table.name for table in self.association_tables]
            if table_name in table_names:
                parameters['operation_type'] = 2
                parameters['transaction_id'] = sa.func.txid_current()
                stmt = (
                    self.metadata.tables[table_name + '_history']
                    .insert()
                    .values(**parameters)
                )
                conn.execute(stmt)
