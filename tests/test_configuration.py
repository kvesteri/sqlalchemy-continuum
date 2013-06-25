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


class TestExclude(TestCase):
    def create_models(self):
        class TextItem(self.Model, Versioned):
            __tablename__ = 'text_item'
            __versioned__ = {
                'exclude': ['content']
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            content = sa.Column(sa.UnicodeText)

        self.TextItem = TextItem

    def test_excluded_columns_not_included_in_history_class(self):
        cls = self.TextItem.__versioned__['class']
        manager = cls._sa_class_manager
        assert 'content' not in manager.keys()

    def test_versioning_with_column_exclusion(self):
        item = self.TextItem(name=u'Some textitem', content=u'Some content')
        self.session.add(item)
        self.session.commit()

        assert item.versions[0].name == u'Some textitem'
