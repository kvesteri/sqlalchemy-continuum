import sqlalchemy as sa
from six import PY3

from tests import TestCase


class TestCommonBaseClass(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

            name = sa.Column('_name', sa.String)

        self.TextItem = TextItem

    def test_insert(self):
        item = self.TextItem(name=u'Something')
        self.session.add(item)
        self.session.commit()
        assert item.versions[0].name == u'Something'

    def test_revert(self):
        item = self.TextItem(name=u'Something')
        self.session.add(item)
        self.session.commit()
        item.name = u'Some other thing'
        self.session.commit()
        item.versions[0].revert()
        self.session.commit()
