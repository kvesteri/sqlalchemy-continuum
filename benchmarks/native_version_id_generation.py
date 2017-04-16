import itertools as it
import warnings
from time import time

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from termcolor import colored

warnings.simplefilter('error', sa.exc.SAWarning)


def test_versioning_strategies(strategy):
    dns = 'postgres://postgres@localhost/sqlalchemy_continuum_test'
    engine = create_engine(dns)
    # engine.echo = True
    connection = engine.connect()

    Session = sessionmaker(bind=connection)
    session = Session(autoflush=False)
    session.execute('CREATE EXTENSION IF NOT EXISTS hstore')
    session.execute('CREATE TABLE IF NOT EXISTS article (id INT)')

    start = time()
    if strategy == 'catch-exception':
        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        BEGIN
            BEGIN
                SELECT id FROM bogus_table;
            EXCEPTION
                WHEN others THEN
                    RETURN NULL;
            END;
        END;
        $$
        LANGUAGE plpgsql
        """)
    elif strategy == 'check-if-table-exists':
        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        DECLARE table_exists BOOL;
        BEGIN
            table_exists = (
                SELECT 1 FROM pg_catalog.pg_class
                WHERE relname = 'bogus_table'
            );
            RETURN NULL;
        END;
        $$
        LANGUAGE plpgsql
        """)
    elif strategy == 'txid-current':
        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        DECLARE tx_id BIGINT;
        BEGIN
            tx_id = (SELECT txid_current() + 5000);
            RETURN NULL;
        END;
        $$
        LANGUAGE plpgsql
        """)
    elif strategy == 'temp-table':
        session.execute('CREATE TEMP TABLE temp_transaction (id BIGINT)')
        session.execute('INSERT INTO temp_transaction (id) VALUES (1)')
        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        DECLARE tx_id BIGINT;
        BEGIN
            tx_id = (SELECT id FROM temp_transaction);
            RETURN NULL;
        END;
        $$
        LANGUAGE plpgsql
        """)


    session.execute("""CREATE TRIGGER article_trigger
        AFTER INSERT OR UPDATE OR DELETE ON article
        FOR EACH ROW EXECUTE PROCEDURE article_audit()""")
    session.commit()

    for i in range(50):
        for i in range(50):
            session.execute('INSERT INTO article (id) VALUES (1)')
        session.commit()

    print 'Testing with:'
    print '   strategy=%r' % strategy
    print colored('%r seconds' % (time() - start), 'red')

    session.execute('DROP TRIGGER article_trigger ON article')
    session.execute('DROP TABLE article CASCADE')
    session.commit()
    session.close_all()
    engine.dispose()
    connection.close()



setting_variants = {
    'strategy': [
        'catch-exception',
        'check-if-table-exists',
        'txid-current',
        'temp-table'
    ],
}


names = sorted(setting_variants)
combinations = [
    dict(zip(names, prod))
    for prod in
    it.product(*(setting_variants[name] for name in names))
]
for combination in combinations:
    test_versioning_strategies(**combination)
