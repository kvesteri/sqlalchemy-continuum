import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


class TestColumnPrefix(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

            __mapper_args__ = {
                'column_prefix': '_'
            }

        self.TextItem = TextItem

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.TextItemVersion = version_class(self.TextItem)

    def test_supports_column_prefix(self):
        assert self.TextItemVersion._id
        assert self.TextItem._id


class TestOrderByWithStringArg(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

            __mapper_args__ = {
                'order_by': 'id',
                'column_prefix': '_'
            }

        self.TextItem = TextItem

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.TextItemVersion = version_class(self.TextItem)

    def test_reflects_order_by(self):
        assert self.TextItemVersion.__mapper_args__['order_by'] == 'id'


class TestOrderByWithInstrumentedAttribute(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

            __mapper_args__ = {
                'order_by': id
            }

        self.TextItem = TextItem

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.TextItemVersion = version_class(self.TextItem)

    def test_reflects_order_by(self):
        assert 'order_by' not in self.TextItemVersion.__mapper_args__
