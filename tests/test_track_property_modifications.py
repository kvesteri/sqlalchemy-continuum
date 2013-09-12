import sqlalchemy as sa
from tests import TestCase


class TestPropertyModificationsTracking(TestCase):
    def create_models(self):
        class User(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, ),
                'track_property_modifications': True
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

        self.User = User

    def test_each_column_generates_additional_mod_column(self):
        UserHistory = self.User.__versioned__['class']
        assert 'name_mod' in UserHistory.__table__.c
        column = UserHistory.__table__.c['name_mod']
        assert not column.nullable
        assert isinstance(column.type, sa.Boolean)
