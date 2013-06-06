import sqlalchemy as sa


def create_postgresql_triggers(pending):
    cls = pending[0]
    first_table = cls.metadata.sorted_tables[0]

    sa.event.listen(
        first_table,
        'before_create',
        sa.schema.DDL("""
        CREATE OR REPLACE FUNCTION
            create_history_record()
            RETURNS TRIGGER AS $$
        BEGIN
            IF (TG_OP = 'UPDATE') THEN
                EXECUTE
                    format(
                        'INSERT INTO %%I VALUES ($1.*, txid_current())',
                        TG_TABLE_NAME || '_history'
                    )
                USING NEW;
                RETURN NEW;
            ELSIF (TG_OP = 'DELETE') THEN
                EXECUTE
                    format(
                        'INSERT INTO %%I VALUES ($1.*, txid_current())',
                        TG_TABLE_NAME || '_history'
                    )
                USING OLD;
                RETURN NEW;
            ELSIF (TG_OP = 'INSERT') THEN
                EXECUTE
                    format(
                        'INSERT INTO %%I VALUES ($1.*, txid_current())',
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
