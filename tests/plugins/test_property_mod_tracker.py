import sqlalchemy as sa
from sqlalchemy_continuum.plugins import PropertyModTrackerPlugin
from tests import TestCase


class TestPropertyModificationsTracking(TestCase):
    plugins = [PropertyModTrackerPlugin]

    def create_models(self):
        class User(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, ),
                'track_property_modifications': True
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column(sa.Unicode(255))

            age = sa.Column(sa.Integer)

        self.User = User

    def test_each_column_generates_additional_mod_column(self):
        UserHistory = self.User.__versioned__['class']
        assert 'name_mod' in UserHistory.__table__.c
        column = UserHistory.__table__.c['name_mod']
        assert not column.nullable
        assert isinstance(column.type, sa.Boolean)

    def test_primary_keys_not_included(self):
        UserHistory = self.User.__versioned__['class']
        assert 'id_mod' not in UserHistory.__table__.c

    def test_mod_properties_get_updated(self):
        user = self.User(name=u'John')
        self.session.add(user)
        self.session.commit()

        assert user.versions[-1].name_mod
