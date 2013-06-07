from copy import copy
import sqlalchemy as sa
from .model_builder import VersionedModelBuilder
from .table_builder import VersionedTableBuilder
from .relationship_builder import VersionedRelationshipBuilder
from .drivers.postgresql import PostgreSQLAdapter
from .versioned import Versioned


def create_transaction_log(cls):
    class TransactionLog(cls.__versioned__['base_classes'][0]):
        __tablename__ = 'transaction_log'
        id = sa.Column(sa.BigInteger, primary_key=True)
        issued_at = sa.Column(sa.DateTime)

    return TransactionLog


def instrument_versioned_classes(mapper, cls):
    if issubclass(cls, Versioned):
        if not cls.__versioned__.get('class') and cls not in cls.__pending__:
            cls.__pending__.append(cls)


def configure_versioned_classes():
    tables = {}

    cls = None
    for cls in Versioned.__pending__:
        existing_table = None
        for class_ in tables:
            if issubclass(cls, class_) and cls.__table__ == class_.__table__:
                existing_table = tables[class_]
                break

        builder = VersionedTableBuilder(cls)
        if existing_table is not None:
            tables[class_] = builder.build_table(existing_table)
        else:
            table = builder.build_table()
            tables[cls] = table

    if cls:
        TransactionLog = create_transaction_log(cls)

    for cls in Versioned.__pending__:
        if cls in tables:
            builder = VersionedModelBuilder(cls)
            builder(tables[cls], TransactionLog)

    if Versioned.__pending__:
        adapter = PostgreSQLAdapter()
        adapter.build_triggers(Versioned.__pending__)

    # Create copy of all pending versioned classes so that we can inspect them
    # later when creating relationships.
    pending_copy = copy(Versioned.__pending__)
    Versioned.__pending__ = []

    # Build relationships for all history classes.
    for cls in pending_copy:
        builder = VersionedRelationshipBuilder(cls)
        builder.build_reflected_relationships()
