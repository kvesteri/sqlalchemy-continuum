from copy import copy
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from .model_builder import VersionedModelBuilder
from .table_builder import VersionedTableBuilder
from .relationship_builder import VersionedRelationshipBuilder


class Versioned(object):
    __versioned__ = {}
    __pending__ = []

    @classmethod
    def __declare_last__(cls):
        if not cls.__versioned__.get('class'):
            cls.__pending__.append(cls)

    @declared_attr
    def transaction_id(cls):
        return sa.Column(
            sa.BigInteger,
            sa.ForeignKey('transaction_log.id', ondelete='CASCADE')
        )


def create_postgresql_triggers(pending):
    cls = pending[0]
    first_table = cls.metadata.sorted_tables[0]

    sa.event.listen(
        first_table,
        'before_create',
        sa.schema.DDL("""
        CREATE FUNCTION
            create_history_record()
            RETURNS TRIGGER AS $$
        BEGIN
            IF (TG_OP = 'UPDATE') THEN
                EXECUTE
                    format(
                        'INSERT INTO %%I VALUES ($1.*)',
                        TG_TABLE_NAME || '_history'
                    )
                USING NEW;
                RETURN NEW;
            ELSIF (TG_OP = 'DELETE') THEN
                EXECUTE
                    format(
                        'INSERT INTO %%I (id) VALUES ($1.id)',
                        TG_TABLE_NAME || '_history'
                    )
                USING OLD;
                RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
                EXECUTE
                    format(
                        'INSERT INTO %%I VALUES ($1.*)',
                        TG_TABLE_NAME || '_history'
                    )
                USING NEW;
                RETURN NEW;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """)
    )
    sa.event.listen(
        first_table,
        'after_drop',
        sa.schema.DDL("""
        DROP FUNCTION create_history_record() CASCADE
        """)
    )
    for cls in pending:
        sa.event.listen(
            cls.__table__,
            'after_create',
            sa.schema.DDL(
                '''
                CREATE TRIGGER %(tablename)s_version_trigger
                AFTER INSERT OR UPDATE OR DELETE ON %(tablename)s
                FOR EACH ROW
                EXECUTE PROCEDURE create_history_record();
                ''' %
                dict(
                    tablename=cls.__tablename__
                )
            )
        )


def configure_versioned():
    tables = {}
    cls = None
    for cls in Versioned.__pending__:
        existing_table = None
        for class_ in tables:
            if issubclass(cls, class_):
                existing_table = tables[class_]
                break

        builder = VersionedTableBuilder(cls)
        if existing_table is not None:
            tables[class_] = builder.build_table(existing_table)
        else:
            table = builder.build_table()
            tables[cls] = table

    if cls:
        class TransactionLog(cls.__versioned__['base_classes'][0]):
            __tablename__ = 'transaction_log'
            id = sa.Column(sa.BigInteger, primary_key=True, autoincrement=True)
            issued_at = sa.Column(sa.DateTime)

    for cls in Versioned.__pending__:
        if cls in tables:
            builder = VersionedModelBuilder(cls)
            builder(tables[cls], TransactionLog)

    if Versioned.__pending__:
        create_postgresql_triggers(Versioned.__pending__)

    # Create copy of all pending versioned classes so that we can inspect them
    # later when creating relationships.
    pending_copy = copy(Versioned.__pending__)
    Versioned.__pending__ = []

    # Build relationships for all history classes.
    for cls in pending_copy:
        builder = VersionedRelationshipBuilder(cls)
        builder.build_reflected_relationships()
        cls.last_transaction = sa.orm.relationship(
            cls.__versioned__['transaction_log']
        )
