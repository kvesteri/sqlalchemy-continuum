import sqlalchemy as sa


def create_postgresql_triggers(pending):
    for cls in pending:
        column_names = [name for name in cls.__table__.c.keys()]
        primary_keys = [
            column.name for column in cls.__table__.c
            if column.primary_key
        ]
        sa.event.listen(
            cls.__table__,
            'before_create',
            sa.schema.DDL("""
            CREATE OR REPLACE FUNCTION
                create_%(tablename)s_history_record()
                RETURNS TRIGGER AS $$
            BEGIN
                IF (TG_OP = 'UPDATE') THEN
                    INSERT INTO %(tablename)s_history
                        (%(column_names)s)
                        VALUES (%(column_values)s, txid_current());
                    RETURN NEW;
                ELSIF (TG_OP = 'DELETE') THEN
                    INSERT INTO %(tablename)s_history
                        (%(primary_keys)s)
                        VALUES
                        (%(primary_key_values)s, txid_current());
                    RETURN NEW;
                ELSIF (TG_OP = 'INSERT') THEN
                    INSERT INTO %(tablename)s_history
                        (%(column_names)s)
                        VALUES (%(column_values)s, txid_current());
                    RETURN NEW;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
            """ %
            dict(
                tablename=cls.__tablename__,
                column_names=', '.join(column_names + ['transaction_id']),
                column_values=', '.join([
                    'NEW.%s' % name for name in column_names
                ]),
                primary_keys=', '.join(primary_keys + ['transaction_id']),
                primary_key_values=', '.join([
                    'OLD.%s' % name for name in primary_keys
                ])
            ))
        )

        sa.event.listen(
            cls.__table__,
            'after_create',
            sa.schema.DDL(
                '''
                CREATE TRIGGER %(tablename)s_version_trigger
                AFTER INSERT OR UPDATE OR DELETE ON %(tablename)s
                FOR EACH ROW
                EXECUTE PROCEDURE create_%(tablename)s_history_record();
                ''' %
                dict(
                    tablename=cls.__tablename__
                )
            )
        )
        sa.event.listen(
            cls.__table__,
            'after_drop',
            sa.schema.DDL(
                """
                DROP FUNCTION create_%(tablename)s_history_record() CASCADE
                """ %
                dict(
                    tablename=cls.__tablename__
                )
            )
        )
