import itertools as it
import warnings
from time import time

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from termcolor import colored

warnings.simplefilter('error', sa.exc.SAWarning)


def test_table_existence(strategy):
    dns = 'postgres://postgres@localhost/sqlalchemy_continuum_test'
    engine = create_engine(dns)
    # engine.echo = True
    connection = engine.connect()

    Session = sessionmaker(bind=connection)
    session = Session(autoflush=False)
    session.execute('CREATE EXTENSION IF NOT EXISTS hstore')
    session.execute(
        'CREATE TABLE IF NOT EXISTS article (id SERIAL PRIMARY KEY, name TEXT)'
    )
    session.execute(
        'CREATE TABLE IF NOT EXISTS article_version (id INT, PRIMARY KEY(id))'
    )

    if strategy == 'insert':
        session.execute(
            'CREATE TABLE IF NOT EXISTS article_version (id INT)'
        )
        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO article_version (id) VALUES (NEW.id);
            RETURN NEW;
        END;
        $$
        LANGUAGE plpgsql
        """)
    elif strategy == 'upsert':
        session.execute(
            'CREATE TABLE IF NOT EXISTS article_version (id INT)'
        )
        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        BEGIN
            WITH upsert as
            (
                UPDATE article_version
                SET id = NEW.id
                WHERE
                    id = NEW.id
                RETURNING *
            )
            INSERT INTO article_version
            (id)
            SELECT
                NEW.id
            WHERE NOT EXISTS (SELECT 1 FROM upsert);

            RETURN NEW;
        END;
        $$
        LANGUAGE plpgsql
        """)
    elif strategy == 'ask-for-forgiveness-insert':
        session.execute(
            'CREATE TABLE IF NOT EXISTS article_version (id INT, PRIMARY KEY(id))'
        )

        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        BEGIN
            BEGIN
                INSERT INTO article_version (id) VALUES (NEW.id);
            EXCEPTION
                WHEN others THEN
                    RAISE EXCEPTION 'asasdad';
            END;

            RETURN NEW;
        END;
        $$
        LANGUAGE plpgsql
        """)

    session.execute("""CREATE TRIGGER article_trigger
        AFTER INSERT OR UPDATE OR DELETE ON article
        FOR EACH ROW EXECUTE PROCEDURE article_audit()""")
    session.commit()

    start = time()
    for i in range(100):
        for i in range(100):
            session.execute("INSERT INTO article (name) VALUES ('a')")
        session.commit()

    print 'Testing strategy %r:' % strategy
    print session.execute('SELECT COUNT(1) FROM article_version').fetchall()
    print colored('%r seconds' % (time() - start), 'red')

    session.execute('DROP TRIGGER article_trigger ON article')
    session.execute('DROP TABLE article CASCADE')
    session.execute('DROP TABLE article_version CASCADE')
    session.commit()
    session.close_all()
    engine.dispose()
    connection.close()



setting_variants = {
    'strategy': [
        'insert',
        'upsert',
        'ask-for-forgiveness-insert',
    ],
}


names = sorted(setting_variants)
combinations = [
    dict(zip(names, prod))
    for prod in
    it.product(*(setting_variants[name] for name in names))
]
for combination in combinations:
    test_table_existence(**combination)
