import sqlalchemy as sa
from sqlalchemy_utils import table_name


class Adapter(object):
    pass


class PostgreSQLAdapter(Adapter):
    def create_version_trigger_procedure_sql(
        self,
        table_name,
        column_names,
        primary_keys
    ):
        return (
            '''
            CREATE OR REPLACE FUNCTION
                create_%(table_name)s_history_record()
                RETURNS TRIGGER AS $$
            BEGIN
                IF (TG_OP = 'UPDATE') THEN
                    IF (NEW != OLD) THEN
                        INSERT INTO %(table_name)s_history
                            (%(column_names)s)
                            VALUES (%(column_values)s, 1, txid_current());
                    END IF;
                    RETURN NEW;
                ELSIF (TG_OP = 'DELETE') THEN
                    INSERT INTO %(table_name)s_history
                        (%(primary_keys)s)
                        VALUES
                        (%(primary_key_values)s, 2, txid_current());
                    RETURN NEW;
                ELSIF (TG_OP = 'INSERT') THEN
                    INSERT INTO %(table_name)s_history
                        (%(column_names)s)
                        VALUES (%(column_values)s, 0, txid_current());
                    RETURN NEW;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
            ''' %
            dict(
                table_name=table_name,
                column_names=', '.join(
                    column_names + ['operation_type', 'transaction_id']
                ),
                column_values=', '.join([
                    'NEW.%s' % name for name in column_names
                ]),
                primary_keys=', '.join(
                    primary_keys + ['operation_type', 'transaction_id']
                ),
                primary_key_values=', '.join([
                    'OLD.%s' % name for name in primary_keys
                ])
            )
        )

    def create_version_trigger_procedure(self, model_class):
        column_names = [name for name in model_class.__table__.c.keys()]
        primary_keys = [
            column.name for column in model_class.__table__.c
            if column.primary_key
        ]

        sa.event.listen(
            model_class.__table__,
            'before_create',
            sa.schema.DDL(
                self.create_version_trigger_procedure_sql(
                    table_name(model_class),
                    column_names,
                    primary_keys
                )
            )
        )

    def create_version_trigger_sql(self, table_name):
        return (
            '''CREATE TRIGGER %(table_name)s_version_trigger
            AFTER INSERT OR UPDATE OR DELETE ON %(table_name)s
            FOR EACH ROW
            EXECUTE PROCEDURE create_%(table_name)s_history_record();
            ''' % dict(table_name=table_name)
        )

    def create_version_trigger(self, model_class):
        sa.event.listen(
            model_class.__table__,
            'after_create',
            sa.schema.DDL(
                self.create_version_trigger_sql(table_name(model_class))
            )
        )

    def drop_version_trigger_sql(self, table_name):
        return (
            '''
            DROP FUNCTION create_%(table_name)s_history_record() CASCADE
            ''' % dict(table_name=table_name)
        )

    def drop_version_trigger(self, model_class):
        sa.event.listen(
            model_class.__table__,
            'after_drop',
            sa.schema.DDL(
                self.drop_version_trigger_sql(table_name(model_class))
            )
        )

    def build_triggers(self, models):
        for model_class in models:
            self.create_version_trigger_procedure(model_class)
            self.create_version_trigger(model_class)
            self.drop_version_trigger(model_class)

    def build_triggers_sql(self, models):
        sql = []
        for model_class in models:
            column_names = [name for name in model_class.__table__.c.keys()]
            primary_keys = [
                column.name for column in model_class.__table__.c
                if column.primary_key
            ]
            tbl_name = table_name(model_class)

            sql += [
                self.create_version_trigger_procedure_sql(
                    tbl_name,
                    column_names,
                    primary_keys
                ),
                self.create_version_trigger_sql(tbl_name),
                self.drop_version_trigger_sql(tbl_name)
            ]
        return sql
