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


def versioned_objects(iterator):
    return [obj for obj in iterator if hasattr(obj, '__versioned__')]


class VersioningManager(object):
    DEFAULT_OPTIONS = {
        'base_classes': None,
        'table_name': '%s_history',
        'revision_column_name': 'revision',
        'transaction_column_name': 'transaction_id',
        'operation_type_column_name': 'operation_type',
        'inspect_column_order': False,
        'relation_naming_function': lambda a: pluralize(underscore(a))
    }

    def __init__(self):
        self.tables = {}
        self.pending_classes = []
        self.history_class_map = {}
        self.meta = None

    @contextmanager
    def tx_meta(self, **meta):
        old_meta = self.meta
        self.meta = meta
        yield
        self.meta = old_meta

    def instrument_versioned_classes(self, mapper, cls):
        if hasattr(cls, '__versioned__'):
            if (not cls.__versioned__.get('class')
                    and cls not in self.pending_classes):
                self.pending_classes.append(cls)

    def declarative_base(self, model):
        for parent in model.__bases__:
            try:
                parent.metadata
                return self.declarative_base(parent)
            except AttributeError:
                pass
        return model

    def create_transaction_log(self, cls):
        naming_func = self.DEFAULT_OPTIONS['relation_naming_function']
        base = self.declarative_base(cls)

        if 'TransactionLog' not in cls._decl_class_registry:
            class TransactionLog(base):
                __tablename__ = 'transaction_log'
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

            return TransactionLog
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
            existing_table = None
            for class_ in self.tables:
                if (issubclass(cls, class_) and
                        cls.__table__ == class_.__table__):
                    existing_table = self.tables[class_]
                    break

            builder = VersionedTableBuilder(self, cls)
            if existing_table is not None:
                self.tables[class_] = builder.build_table(existing_table)
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

    def configure_versioned_classes(self):
        self.build_tables()
        self.build_models()
        self.build_triggers()

        # Create copy of all pending versioned classes so that we can inspect
        # them later when creating relationships.
        pending_copy = copy(self.pending_classes)
        self.pending_classes = []
        self.build_relationships(pending_copy)

    def create_transaction_log_entries(self, session):
        iterator = itertools.chain(session.new, session.dirty, session.deleted)
        transaction_log_cls = None
        for obj in versioned_objects(iterator):
            transaction_log_cls = obj.__versioned__['transaction_log']
            break

        if transaction_log_cls:
            session.add(
                transaction_log_cls(
                    id=sa.func.txid_current(),
                    issued_at=sa.func.now(),
                    meta=self.meta
                )
            )

    def create_transaction_changes_entries(self, session):
        iterator = itertools.chain(session.new, session.dirty, session.deleted)
        changed_entities = set([])
        for obj in versioned_objects(iterator):
            changed_entities.add(obj.__class__)
        for entity in changed_entities:
            session.execute(
                '''INSERT INTO transaction_changes
                (transaction_id, entity_name)
                VALUES (txid_current(), :entity_name)''',
                {'entity_name': entity.__name__}
            )
