import inspect
import itertools as it
import os
import warnings
from copy import copy

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    close_all_sessions,
    column_property,
    declarative_base,
    sessionmaker,
)

from sqlalchemy_continuum import (
    ClassNotVersioned,
    make_versioned,
    remove_versioning,
    version_class,
    versioning_manager,
)
from sqlalchemy_continuum.plugins import TransactionChangesPlugin, TransactionMetaPlugin
from sqlalchemy_continuum.transaction import TransactionFactory

warnings.simplefilter('error', sa.exc.SAWarning)


class QueryPool:
    queries = []


@sa.event.listens_for(sa.engine.Engine, 'before_cursor_execute')
def log_sql(conn, cursor, statement, parameters, context, executemany):
    QueryPool.queries.append(statement)


def get_url_from_driver(driver):
    url = os.environ.get('DATABASE_URL')
    if url:
        return url

    if driver == 'postgres':
        return 'postgresql://postgres:postgres@localhost/main'
    elif driver == 'mysql':
        # NB username is also in create_schema
        return 'mysql+pymysql://root@localhost/main'
    elif driver == 'sqlite':
        return 'sqlite:///:memory:'
    else:
        raise Exception(f'Unknown driver given: {driver!r}')


def get_driver_name(driver):
    return driver[0 : -len('-native')] if driver.endswith('-native') else driver


def uses_native_versioning():
    return os.environ.get('DB', 'sqlite').endswith('-native')


class TestCase:
    versioning_strategy = 'subquery'
    transaction_column_name = 'transaction_id'
    end_transaction_column_name = 'end_transaction_id'
    composite_pk = False
    plugins = [TransactionChangesPlugin(), TransactionMetaPlugin()]
    transaction_cls = TransactionFactory()
    user_cls = None
    should_create_models = True

    @property
    def options(self):
        return {
            'create_models': self.should_create_models,
            'native_versioning': uses_native_versioning(),
            'base_classes': (self.Model,),
            'strategy': self.versioning_strategy,
            'transaction_column_name': self.transaction_column_name,
            'end_transaction_column_name': self.end_transaction_column_name,
        }

    def setup_method(self, method):
        self.Model = declarative_base()
        make_versioned(options=self.options)

        driver = os.environ.get('DB', 'sqlite')
        self.driver = get_driver_name(driver)
        versioning_manager.plugins = self.plugins
        versioning_manager.transaction_cls = self.transaction_cls
        versioning_manager.user_cls = self.user_cls

        self.engine = create_engine(get_url_from_driver(self.driver), echo=True)
        # self.engine.echo = True
        self.create_models()

        sa.orm.configure_mappers()

        if hasattr(self, 'Article'):
            try:
                self.ArticleVersion = version_class(self.Article)
            except ClassNotVersioned:
                pass
        if hasattr(self, 'Tag'):
            try:
                self.TagVersion = version_class(self.Tag)
            except ClassNotVersioned:
                pass

        self.connection = self.engine.connect()
        Session = sessionmaker(bind=self.connection)
        self.session = Session(autoflush=False)

        if driver == 'postgres-native':
            self.session.execute(sa.text('CREATE EXTENSION IF NOT EXISTS hstore'))

        # Run any other custom SQL in here
        self.create_schema('other')
        self.session.commit()

        # Using an engine here instead of connection will call commit for us,
        # which lets us use the same syntax for 1.4 and 2.0
        self.Model.metadata.create_all(self.engine)

    def teardown_method(self, method):
        self.session.rollback()
        uow_leaks = versioning_manager.units_of_work
        session_map_leaks = versioning_manager.session_connection_map

        remove_versioning()
        QueryPool.queries = []
        versioning_manager.reset()

        try:
            close_all_sessions()
        except Exception:
            pass
        self.session.expunge_all()

        self.Model.metadata.drop_all(self.engine)

        self.drop_schema('other')
        self.session.commit()

        self.connection.close()
        self.engine.dispose()

        assert not uow_leaks
        assert not session_map_leaks

    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

            # Dynamic column cotaining all text content data
            fulltext_content = column_property(name + content + description)

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(Article, backref='tags')

        self.Article = Article
        self.Tag = Tag

    def create_schema(self, schema):
        if self.driver == 'postgres':
            self.session.execute(sa.text(f'CREATE SCHEMA {schema}'))

        elif self.driver == 'mysql':
            self.session.execute(sa.text(f'CREATE DATABASE {schema}'))
            # This user must match the value in get_url_from_driver
            self.session.execute(sa.text(f'GRANT ALL PRIVILEGES ON {schema}.* TO root'))

        elif self.driver == 'sqlite':
            self.session.execute(sa.text(f"ATTACH DATABASE ':memory:' AS {schema}"))

        else:
            raise NotImplementedError

    def drop_schema(self, schema):
        if self.driver == 'postgres':
            self.session.execute(sa.text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))

        elif self.driver == 'mysql':
            self.session.execute(sa.text(f'DROP DATABASE IF EXISTS {schema}'))

        elif self.driver == 'sqlite':
            self.session.execute(sa.text(f'DETACH DATABASE {schema}'))

        else:
            raise NotImplementedError


setting_variants = {
    'versioning_strategy': [
        'subquery',
        'validity',
    ],
    'transaction_column_name': ['transaction_id', 'tx_id'],
    'end_transaction_column_name': ['end_transaction_id', 'end_tx_id'],
}


def create_test_cases(base_class, setting_variants=setting_variants):
    """
    Function for creating bunch of test case classes for given base class
    and setting variants. Number of test cases created is the number of linear
    combinations with setting variants.

    :param base_class:
        Base test case class, should be in format 'xxxTestCase'
    :param setting_variants:
        A dictionary with keys as versioned configuration option keys and
        values as list of possible option values.
    """
    names = sorted(setting_variants)
    combinations = [
        dict(zip(names, prod))
        for prod in it.product(*(setting_variants[name] for name in names))
    ]

    # Get the module where this function was called in.
    frm = inspect.stack()[1]
    module = inspect.getmodule(frm[0])

    class_suffix = base_class.__name__[0 : -len('TestCase')]
    for index, combination in enumerate(combinations):
        class_name = f'Test{class_suffix}{index}'
        # Assign a new test case class for current module.
        setattr(module, class_name, type(class_name, (base_class,), combination))
