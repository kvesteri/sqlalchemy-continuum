from contextlib import contextmanager
from inflection import underscore, pluralize
from copy import copy
import sqlalchemy as sa
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import HSTORE
from .model_builder import VersionedModelBuilder
from .table_builder import VersionedTableBuilder
from .relationship_builder import VersionedRelationshipBuilder
from .unit_of_work import UnitOfWork


class VersioningManager(object):
    def __init__(
        self,
    ):
        self.uow = UnitOfWork(self)
        self.reset()

    def reset(self):
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
        self.uow.reset()

        self.metadata = None
        self.options = {
            'versioning': True,
            'base_classes': None,
            'table_name': '%s_history',
            'exclude': [],
            'include': [],
            'transaction_column_name': 'transaction_id',
            'operation_type_column_name': 'operation_type',
            'relation_naming_function': lambda a: pluralize(underscore(a))
        }

    @contextmanager
    def tx_context(self, **tx_context):
        old_tx_context = self.uow.tx_context
        self.uow.tx_context = tx_context
        yield
        self.uow.tx_context = old_tx_context

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

    def build_models(self):
        if self.pending_classes:
            cls = self.pending_classes[0]
            self.transaction_log_cls = self.create_transaction_log(cls)
            self.transaction_changes_cls = self.create_transaction_changes(
                cls, self.transaction_log_cls
            )

            for cls in self.pending_classes:
                if not self.option(cls, 'versioning'):
                    continue

                if cls in self.tables:
                    builder = VersionedModelBuilder(self, cls)
                    builder(
                        self.tables[cls],
                        self.transaction_log_cls,
                        self.transaction_changes_cls
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

        # Create copy of all pending versioned classes so that we can inspect
        # them later when creating relationships.
        pending_copy = copy(self.pending_classes)
        self.pending_classes = []
        self.build_relationships(pending_copy)

        for cls in pending_copy:
            # set the "active_history" flag
            for prop in cls.__mapper__.iterate_properties:
                getattr(cls, prop.key).impl.active_history = True
