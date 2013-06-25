from flask import Flask, url_for
from flask.ext.login import LoginManager
import sqlalchemy as sa
from sqlalchemy_continuum import (
    make_versioned, versioning_manager, Versioned
)
from sqlalchemy_continuum.ext.flask import (
    versioning_manager as flask_versioning_manager
)
from tests import TestCase


make_versioned(manager=flask_versioning_manager)


class TestFlaskVersioningManager(TestCase):
    def setup_class(cls):
        versioning_manager.options['versioning'] = False
        flask_versioning_manager.options['versioning'] = True

    def teardown_class(cls):
        versioning_manager.options['versioning'] = True
        flask_versioning_manager.options['versioning'] = False

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

    def login(self, user):
        """
        Log in the user returned by :meth:`create_user`.

        :returns: the logged in user
        """
        with self.client.session_transaction() as s:
            s['user_id'] = user.id
        return user

    def logout(self, user=None):
        with self.client.session_transaction() as s:
            s['user_id'] = None

    def create_models(self):
        TestCase.create_models(self)

        class User(self.Model, Versioned):
            __tablename__ = 'user'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
        self.User = User

    def setup_views(self):
        @self.app.route('/')
        def index():
            article = self.Article()
            article.name = u'Some article'
            self.session.add(article)
            self.session.commit()
            return ''

    def test_versioning_inside_request(self):
        user = self.User(name=u'Rambo')
        self.session.add(user)
        self.session.commit()
        self.login(user)
        self.client.get(url_for('.index'))

        article = self.session.query(self.Article).first()
        tx = article.versions[-1].transaction
        assert tx.user.id == user.id
