from copy import copy
import inspect
import itertools as it
import os
import warnings
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy_continuum import (
    ClassNotVersioned,
    version_class,
    make_versioned,
    versioning_manager,
    remove_versioning
)
from sqlalchemy_continuum.transaction import TransactionFactory
from sqlalchemy_continuum.plugins import (
    TransactionMetaPlugin,
    TransactionChangesPlugin
)

warnings.simplefilter('error', sa.exc.SAWarning)


class QueryPool(object):
    queries = []


@sa.event.listens_for(sa.engine.Engine, 'before_cursor_execute')
def log_sql(
    conn,
    cursor,
    statement,
    parameters,
    context,
    executemany
):
    QueryPool.queries.append(statement)


def get_dns_from_driver(driver):
    if driver == 'postgres':
        return 'postgres://postgres@localhost/sqlalchemy_continuum_test'
    elif driver == 'mysql':
        return 'mysql+pymysql://travis@localhost/sqlalchemy_continuum_test'
    elif driver == 'sqlite':
        return 'sqlite:///:memory:'
    else:
        raise Exception('Unknown driver given: %r' % driver)


def get_driver_name(driver):
    return driver[0:-len('-native')] if driver.endswith('-native') else driver


def uses_native_versioning():
    return os.environ.get('DB', 'sqlite').endswith('-native')


class TestCase(object):
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
            'base_classes': (self.Model, ),
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

        self.engine = create_engine(get_dns_from_driver(self.driver))
        # self.engine.echo = True
        self.create_models()

        sa.orm.configure_mappers()

        self.connection = self.engine.connect()

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
        self.create_tables()

        Session = sessionmaker(bind=self.connection)
        self.session = Session(autoflush=False)
        if driver == 'postgres-native':
            self.session.execute('CREATE EXTENSION IF NOT EXISTS hstore')

    def create_tables(self):
        self.Model.metadata.create_all(self.connection)

    def drop_tables(self):
        self.Model.metadata.drop_all(self.connection)

    def teardown_method(self, method):
        remove_versioning()
        QueryPool.queries = []
        versioning_manager.reset()

        self.session.close_all()
        self.session.expunge_all()
        self.drop_tables()
        self.engine.dispose()
        self.connection.close()

    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(Article, backref='tags')

        self.Article = Article
        self.Tag = Tag


setting_variants = {
    'versioning_strategy': [
        'subquery',
        'validity',
    ],
    'transaction_column_name': [
        'transaction_id',
        'tx_id'
    ],
    'end_transaction_column_name': [
        'end_transaction_id',
        'end_tx_id'
    ]
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
        for prod in
        it.product(*(setting_variants[name] for name in names))
    ]

    # Get the module where this function was called in.
    frm = inspect.stack()[1]
    module = inspect.getmodule(frm[0])

    class_suffix = base_class.__name__[0:-len('TestCase')]
    for index, combination in enumerate(combinations):
        class_name = 'Test%s%i' % (class_suffix, index)
        # Assign a new test case class for current module.
        setattr(
            module,
            class_name,
            type(
                class_name,
                (base_class, ),
                combination
            )
        )
