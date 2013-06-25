import sqlalchemy as sa
from sqlalchemy_continuum import Versioned
from tests import TestCase


class TestVersionedModelWithoutVersioning(TestCase):
    def create_models(self):
        class TextItem(self.Model, Versioned):
            __tablename__ = 'text_item'
            __versioned__ = {
                'versioning': False
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.TextItem = TextItem

    def test_does_not_create_history_class_when_versioning_turned_off(self):
        assert 'class' not in self.TextItem.__versioned__
