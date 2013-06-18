import sqlalchemy as sa
from sqlalchemy import Table, MetaData


class Adapter(object):
    pass


class TriggerBuilder(object):
    skipped_columns = ['revision', 'operation_type', 'transaction_id']

    def __init__(self, table):
        self.table = table

    @property
    def parent_table(self):
        return self.table.metadata.tables[
            self.table.name[:-len('_history')]
        ]

    @property
    def column_names(self):
        return [
            '"%s"' % name for name in self.table.c.keys()
            if name not in self.skipped_columns
        ]

    @property
    def primary_keys(self):
        return [
            '"%s"' % column.name for column in self.parent_table.c
            if column.primary_key
        ]

    @property
    def create_trigger_procedure_sql(self):
        return (
            '''
            CREATE OR REPLACE FUNCTION
                create_%(table_name)s_record()
                RETURNS TRIGGER AS $$
            BEGIN
                IF (TG_OP = 'UPDATE') THEN
                    IF (NEW != OLD) THEN
                        INSERT INTO %(table_name)s
                            (%(column_names)s)
                            VALUES (%(column_values)s, 1, txid_current());
                    END IF;
                    RETURN NEW;
                ELSIF (TG_OP = 'DELETE') THEN
                    INSERT INTO %(table_name)s
                        (%(primary_keys)s)
                        VALUES
                        (%(primary_key_values)s, 2, txid_current());
                    RETURN NEW;
                ELSIF (TG_OP = 'INSERT') THEN
                    INSERT INTO %(table_name)s
                        (%(column_names)s)
                        VALUES (%(column_values)s, 0, txid_current());
                    RETURN NEW;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
            ''' %
            dict(
                table_name=self.table.name,
                column_names=', '.join(
                    self.column_names + self.skipped_columns[1:]
                ),
                column_values=', '.join([
                    'NEW.%s' % name for name in self.column_names
                ]),
                primary_keys=', '.join(
                    self.primary_keys + self.skipped_columns[1:]
                ),
                primary_key_values=', '.join([
                    'OLD.%s' % name for name in self.primary_keys
                ])
            )
        )

    @property
    def create_trigger_sql(self):
        return (
            '''CREATE TRIGGER %(table_name)s_version_trigger
            AFTER INSERT OR UPDATE OR DELETE ON "%(table_name)s"
            FOR EACH ROW
            EXECUTE PROCEDURE create_%(table_name)s_history_record();
            ''' % dict(
            table_name=self.table.name[:-len('_history')]
        ))

    @property
    def drop_trigger_procedure_sql(self):
        return (
            '''
            DROP FUNCTION create_%(table_name)s_record() CASCADE
            ''' % dict(table_name=self.table.name)
        )

    def attach_trigger_procedure_listener(self):
        sa.event.listen(
            self.parent_table,
            'before_create',
            sa.schema.DDL(self.create_trigger_procedure_sql)
        )

    def attach_trigger_listener(self):
        sa.event.listen(
            self.parent_table,
            'after_create',
            sa.schema.DDL(
                self.create_trigger_sql
            )
        )

    def attach_drop_trigger_listener(self):
        sa.event.listen(
            self.parent_table,
            'after_drop',
            sa.schema.DDL(
                self.drop_trigger_procedure_sql
            )
        )


class TriggerSynchronizer(object):
    def __init__(self, op, table_name):
        self.op = op
        self.table_name = table_name
        metadata = MetaData(bind=self.op.get_bind())
        table = Table(
            table_name,
            metadata,
            autoload=True
        )
        Table(
            table_name[0:-len('_history')],
            metadata,
            autoload=True
        )
        self.builder = TriggerBuilder(table)

    def sync_create_table(self):
        self.op.execute(self.builder.create_trigger_procedure_sql)
        self.op.execute(self.builder.create_trigger_sql)

    def sync_drop_table(self):
        self.op.execute(self.builder.drop_trigger_procedure_sql)

    def sync_alter_table(self):
        self.op.execute(self.builder.drop_trigger_procedure_sql)
        self.op.execute(self.builder.create_trigger_procedure_sql)


class PostgreSQLAdapter(Adapter):
    builder_class = TriggerBuilder

    def build_triggers(self, models):
        # In order to support single table inheritance we need keep track of
        # already visited tables so that triggers don't get created multiple
        # times for same table.
        visited_tables = []
        for model_class in models:
            table = model_class.__versioned__['class'].__table__
            if table in visited_tables:
                continue
            builder = self.builder_class(table)
            builder.attach_trigger_procedure_listener()
            builder.attach_trigger_listener()
            builder.attach_drop_trigger_listener()
            visited_tables.append(table)

    def build_triggers_sql(self, models):
        sql = []
        for model_class in models:
            table = model_class.__versioned__['class'].__table__
            builder = self.builder_class(table)
            sql += [
                builder.create_trigger_procedure_sql,
                builder.create_trigger_sql,
                builder.drop_trigger_procedure_sql
            ]
        return sql
