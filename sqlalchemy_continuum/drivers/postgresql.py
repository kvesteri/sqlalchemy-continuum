import sqlalchemy as sa


class Adapter(object):
    pass


class TableTriggerBuilder(object):
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
            name for name in self.table.c.keys()
            if name not in ['operation_type', 'transaction_id']
        ]

    @property
    def primary_keys(self):
        return [
            column.name for column in self.table.c
            if (
                column.primary_key and
                column.name not in ['operation_type', 'transaction_id']
            )
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
                    self.column_names + ['operation_type', 'transaction_id']
                ),
                column_values=', '.join([
                    'NEW.%s' % name for name in self.column_names
                ]),
                primary_keys=', '.join(
                    self.primary_keys + ['operation_type', 'transaction_id']
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
            AFTER INSERT OR UPDATE OR DELETE ON %(table_name)s
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


class PostgreSQLAdapter(Adapter):
    builder_class = TableTriggerBuilder

    def build_triggers(self, models):
        for model_class in models:
            table = model_class.__versioned__['class'].__table__
            builder = self.builder_class(table)
            builder.attach_trigger_procedure_listener()
            builder.attach_trigger_listener()
            builder.attach_drop_trigger_listener()

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
