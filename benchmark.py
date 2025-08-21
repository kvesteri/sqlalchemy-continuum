import itertools as it
import warnings
from copy import copy
from time import time

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions, declarative_base, sessionmaker
from termcolor import colored

from sqlalchemy_continuum import make_versioned, remove_versioning, versioning_manager
from sqlalchemy_continuum.plugins import (
    PropertyModTrackerPlugin,
    TransactionChangesPlugin,
    TransactionMetaPlugin,
)
from sqlalchemy_continuum.transaction import TransactionFactory

warnings.simplefilter('error', sa.exc.SAWarning)


def test_versioning(native_versioning, versioning_strategy, property_mod_tracking):
    transaction_column_name = 'transaction_id'
    end_transaction_column_name = 'end_transaction_id'
    plugins = [TransactionChangesPlugin(), TransactionMetaPlugin()]

    if property_mod_tracking:
        plugins.append(PropertyModTrackerPlugin())
    transaction_cls = TransactionFactory()
    user_cls = None

    Model = declarative_base()

    options = {
        'create_models': True,
        'native_versioning': native_versioning,
        'base_classes': (Model,),
        'strategy': versioning_strategy,
        'transaction_column_name': transaction_column_name,
        'end_transaction_column_name': end_transaction_column_name,
    }

    make_versioned(options=options)

    dns = 'postgresql://postgres:postgres@localhost/main'
    versioning_manager.plugins = plugins
    versioning_manager.transaction_cls = transaction_cls
    versioning_manager.user_cls = user_cls

    engine = create_engine(dns)
    # engine.echo = True

    class Article(Model):
        __tablename__ = 'article'
        __versioned__ = copy(options)

        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
        name = sa.Column(sa.Unicode(255), nullable=False)
        content = sa.Column(sa.UnicodeText)
        description = sa.Column(sa.UnicodeText)

    class Tag(Model):
        __tablename__ = 'tag'
        __versioned__ = copy(options)

        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
        article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
        article = sa.orm.relationship(Article, backref='tags')

    sa.orm.configure_mappers()

    connection = engine.connect()

    Model.metadata.create_all(connection)

    Session = sessionmaker(bind=connection)
    session = Session(autoflush=False)
    session.execute('CREATE EXTENSION IF NOT EXISTS hstore')

    Model.metadata.create_all(connection)

    start = time()

    for i in range(20):
        for i in range(20):
            session.add(Article(name='Article', tags=[Tag(), Tag()]))
        session.commit()

    print('Testing with:')
    print(f'   native_versioning={native_versioning!r}')
    print(f'   versioning_strategy={versioning_strategy!r}')
    print(f'   property_mod_tracking={property_mod_tracking!r}')
    print(colored(f'{time() - start!r} seconds', 'red'))

    Model.metadata.drop_all(connection)

    remove_versioning()
    versioning_manager.reset()

    close_all_sessions()
    session.expunge_all()
    Model.metadata.drop_all(connection)
    engine.dispose()
    connection.close()


setting_variants = {
    'versioning_strategy': [
        'subquery',
        'validity',
    ],
    'native_versioning': [True, False],
    'property_mod_tracking': [False, True],
}


names = sorted(setting_variants)
combinations = [
    dict(zip(names, prod))
    for prod in it.product(*(setting_variants[name] for name in names))
]
for combination in combinations:
    test_versioning(**combination)
