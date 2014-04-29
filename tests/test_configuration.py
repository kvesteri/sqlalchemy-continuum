from pytest import raises
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_continuum import (
    versioning_manager, ImproperlyConfigured, TransactionFactory
)

from tests import TestCase


class TestVersionedModelWithoutVersioning(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'versioning': False
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.TextItem = TextItem

    def test_does_not_create_history_class(self):
        assert 'class' not in self.TextItem.__versioned__

    def test_does_not_create_history_table(self):
        assert 'text_item_history' not in self.Model.metadata.tables

    def test_does_add_objects_to_unit_of_work(self):
        self.session.add(self.TextItem())
        self.session.commit()


class TestWithUnknownUserClass(TestCase):
    def test_something(self):
        self.Model = declarative_base()

        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.TextItem = TextItem

        versioning_manager.user_cls = 'User'
        versioning_manager.declarative_base = self.Model

        factory = TransactionFactory()
        with raises(ImproperlyConfigured):
            factory(versioning_manager)

    def teardown_method(self, method):
        pass

    def setup_method(self, method):
        pass
