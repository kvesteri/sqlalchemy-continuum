import os

import sqlalchemy as sa
from flask import Flask, url_for
from flask_login import LoginManager, UserMixin, login_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import close_all_sessions

from sqlalchemy_continuum import make_versioned, remove_versioning, versioning_manager
from sqlalchemy_continuum.plugins import FlaskPlugin
from sqlalchemy_continuum.transaction import TransactionFactory
from tests import TestCase, get_driver_name, get_url_from_driver, uses_native_versioning


class TestFlaskPluginConfiguration:
    def test_set_factories(self):
        def some_func():
            return None

        def some_other_func():
            return None

        plugin = FlaskPlugin(
            current_user_id_factory=some_func, remote_addr_factory=some_other_func
        )
        assert plugin.current_user_id_factory is some_func
        assert plugin.remote_addr_factory is some_other_func


class TestFlaskPlugin(TestCase):
    plugins = [FlaskPlugin()]
    transaction_cls = TransactionFactory()
    user_cls = 'User'

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.app = Flask(__name__)
        self.app.secret_key = 'secret'
        self.app.debug = True
        self.setup_views()
        login_manager = LoginManager()
        login_manager.init_app(self.app)
        self.client = self.app.test_client()
        self.context = self.app.test_request_context()
        self.context.push()

        @login_manager.user_loader
        def load_user(id):
            return self.session.query(self.User).get(id)

    def teardown_method(self, method):
        TestCase.teardown_method(self, method)
        self.context.pop()
        self.context = None
        self.client = None
        self.app = None

    def create_models(self):
        TestCase.create_models(self)

        class User(self.Model, UserMixin):
            __tablename__ = 'user'
            __versioned__ = {'base_classes': (self.Model,)}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)

        self.User = User

    def setup_views(self):
        @self.app.route('/simple-flush')
        def test_simple_flush():
            article = self.Article()
            article.name = 'Some article'
            self.session.add(article)
            self.session.commit()
            return ''

        @self.app.route('/raw-sql-and-flush')
        def test_raw_sql_and_flush():
            self.session.execute(
                sa.text("INSERT INTO article (name) VALUES ('some article')")
            )
            article = self.Article()
            article.name = 'Some article'
            self.session.add(article)
            self.session.flush()
            self.session.execute(
                sa.text("INSERT INTO article (name) VALUES ('some article')")
            )
            self.session.commit()
            return ''

    def test_versioning_inside_request(self):
        user = self.User(name='Rambo')
        self.session.add(user)
        self.session.commit()
        login_user(user)
        self.client.get(url_for('.test_simple_flush'))

        article = self.session.query(self.Article).first()
        tx = list(article.versions)[-1].transaction
        assert tx.user.id == user.id

    def test_raw_sql_and_flush(self):
        user = self.User(name='Rambo')
        self.session.add(user)
        self.session.commit()
        login_user(user)
        self.client.get(url_for('.test_raw_sql_and_flush'))
        assert self.session.query(versioning_manager.transaction_cls).count() == 2


class TestFlaskPluginWithoutRequestContext(TestCase):
    plugins = [FlaskPlugin()]
    user_cls = 'User'

    def create_models(self):
        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = {'base_classes': (self.Model,)}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)

        self.User = User

        TestCase.create_models(self)

    def test_versioning_outside_request(self):
        user = self.User(name='Rambo')
        self.session.add(user)
        self.session.commit()


class TestFlaskPluginWithFlaskSQLAlchemyExtension:
    versioning_strategy = 'validity'

    def create_models(self):
        class User(self.db.Model):
            __tablename__ = 'user'
            __versioned__ = {'base_classes': (self.db.Model,)}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)

        class Article(self.db.Model):
            __tablename__ = 'article'
            __versioned__ = {'base_classes': (self.db.Model,)}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        article_tag = sa.Table(
            'article_tag',
            self.db.Model.metadata,
            sa.Column(
                'article_id',
                sa.Integer,
                sa.ForeignKey('article.id'),
                primary_key=True,
            ),
            sa.Column('tag_id', sa.Integer, sa.ForeignKey('tag.id'), primary_key=True),
        )

        class Tag(self.db.Model):
            __tablename__ = 'tag'
            __versioned__ = {'base_classes': (self.db.Model,)}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        Tag.articles = sa.orm.relationship(
            Article, secondary=article_tag, backref='tags'
        )

        self.User = User
        self.Article = Article
        self.Tag = Tag

    def setup_method(self, method):
        self.db = SQLAlchemy()
        make_versioned()

        versioning_manager.transaction_cls = TransactionFactory()
        versioning_manager.options['native_versioning'] = uses_native_versioning()

        self.create_models()

        sa.orm.configure_mappers()

        self.app = Flask(__name__)
        # self.app.config['SQLALCHEMY_ECHO'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = get_url_from_driver(
            get_driver_name(os.environ.get('DB', 'sqlite'))
        )
        self.db.init_app(self.app)
        self.app.secret_key = 'secret'
        self.app.debug = True
        self.client = self.app.test_client()
        self.context = self.app.test_request_context()
        self.context.push()
        self.db.create_all()
        self.db.session.commit()

    def teardown_method(self, method):
        remove_versioning()
        self.db.session.remove()
        self.db.drop_all()
        self.db.session.commit()
        close_all_sessions()
        self.db.engine.dispose()
        self.context.pop()
        self.context = None
        self.client = None
        self.app = None

    def test_version_relations(self):
        article = self.Article()
        article.name = 'Some article'
        article.content = 'Some content'
        self.db.session.add(article)
        self.db.session.commit()
        assert not article.versions[0].tags

    def test_single_insert(self):
        article = self.Article()
        article.name = 'Some article'
        article.content = 'Some content'
        tag = self.Tag(name='some tag')
        article.tags.append(tag)
        self.db.session.add(article)
        self.db.session.commit()
        assert len(article.versions[0].tags) == 1

    def test_create_transaction_with_scoped_session(self):
        article = self.Article()
        article.name = 'Some article'
        article.content = 'Some content'
        self.db.session.add(article)
        uow = versioning_manager.unit_of_work(self.db.session)
        transaction = uow.create_transaction(self.db.session)
        assert transaction.id
