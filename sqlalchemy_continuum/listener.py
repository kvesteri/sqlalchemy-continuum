from inflection import underscore, pluralize
from copy import copy
import sqlalchemy as sa
from .model_builder import VersionedModelBuilder
from .table_builder import VersionedTableBuilder
from .relationship_builder import VersionedRelationshipBuilder
from .drivers.postgresql import PostgreSQLAdapter
from .versioned import Versioned


class VersioningManager(object):
    DEFAULT_OPTIONS = {
        'base_classes': None,
        'table_name': '%s_history',
        'version_column_name': 'transaction_id',
        'inspect_column_order': False,
        'relation_naming_function': lambda a: pluralize(underscore(a))
    }

    def __init__(self):
        self.tables = {}
        self.pending_classes = []
        self.history_class_map = {}

    def instrument_versioned_classes(self, mapper, cls):
        if issubclass(cls, Versioned):
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

        class TransactionLog(self.declarative_base(cls)):
            __tablename__ = 'transaction_log'
            id = sa.Column(sa.BigInteger, primary_key=True)
            issued_at = sa.Column(sa.DateTime)

            @property
            def all_affected_entities(obj_self):
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

            for cls in self.pending_classes:
                if cls in self.tables:
                    builder = VersionedModelBuilder(self, cls)
                    builder(self.tables[cls], TransactionLog)

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


def make_versioned(mapper, manager_class=VersioningManager):
    manager = manager_class()
    sa.event.listen(
        mapper, 'instrument_class', manager.instrument_versioned_classes
    )
    sa.event.listen(
        mapper, 'after_configured', manager.configure_versioned_classes
    )
