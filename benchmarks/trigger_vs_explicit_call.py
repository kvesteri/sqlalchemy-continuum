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
        'CREATE TABLE IF NOT EXISTS article (id INT)'
    )
    session.execute(
        'CREATE TABLE IF NOT EXISTS article_version (id INT)'
    )

    start = time()
    if strategy == 'trigger':
        session.execute("""
        CREATE OR REPLACE FUNCTION article_audit() RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO article_version (id) VALUES (NEW.id);
            RETURN NEW;
        END;
        $$
        LANGUAGE plpgsql
        """)

        session.execute("""CREATE TRIGGER article_trigger
            AFTER INSERT OR UPDATE OR DELETE ON article
            FOR EACH ROW EXECUTE PROCEDURE article_audit()""")
    session.commit()


    for i in range(10000):
        session.execute("INSERT INTO article (id) VALUES (1)")
        if strategy == 'explicit-call':
            session.execute("INSERT INTO article_version (id) VALUES (1)")
    session.commit()

    print 'Testing strategy %r:' % strategy
    print colored('%r seconds' % (time() - start), 'red')

    session.execute('DROP TRIGGER IF EXISTS article_trigger ON article')
    session.execute('DROP TABLE article CASCADE')
    session.execute('DROP TABLE article_version CASCADE')
    session.commit()
    session.close_all()
    engine.dispose()
    connection.close()



setting_variants = {
    'strategy': [
        'trigger',
        'explicit-call',
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
