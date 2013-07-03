from datetime import datetime
import sqlalchemy as sa
from tests import TestCase


class TestDateTimeColumnExclusion(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            created_at = sa.Column(sa.DateTime, default=datetime.now)

        self.Article = Article

    def test_datetime_columns_with_defaults_excluded_by_default(self):
        assert (
            'created_at' not in
            self.Article.__versioned__['class'].__table__.c
        )


class TestDateTimeColumnInclusion(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'include': 'created_at'
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            created_at = sa.Column(sa.DateTime, default=datetime.now)

        self.Article = Article

    def test_datetime_columns_with_defaults_excluded_by_default(self):
        assert (
            'created_at' in
            self.Article.__versioned__['class'].__table__.c
        )


class TestColumnExclusion(TestCase):
    def create_models(self):
        class TextItem(self.Model):
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
