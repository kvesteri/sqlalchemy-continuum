from datetime import datetime
from pytest import mark
import sqlalchemy as sa
from sqlalchemy_utils import TSVectorType
from sqlalchemy_continuum import history_class
from tests import TestCase


class TestDateTimeColumnExclusion(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            created_at = sa.Column(sa.DateTime, default=datetime.now)
            creation_date = sa.Column(
                sa.Date, default=lambda: datetime.now().date
            )
            is_deleted = sa.Column(sa.Boolean, default=False)

        self.Article = Article

    def test_datetime_columns_with_defaults_excluded_by_default(self):
        assert (
            'created_at' not in
            history_class(self.Article).__table__.c
        )

    def test_date_columns_with_defaults_excluded_by_default(self):
        assert (
            'creation_date' not in
            history_class(self.Article).__table__.c
        )

    def test_datetime_exclusion_only_applies_to_datetime_types(self):
        assert (
            'is_deleted' in
            history_class(self.Article).__table__.c
        )


@mark.skipif("os.environ.get('DB') != 'postgres'")
class TestTSVectorTypeColumnExclusion(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            search_vector = sa.Column(TSVectorType)

        self.Article = Article

    def test_tsvector_typed_columns_excluded_by_default(self):
        assert (
            'search_vector' not in
            history_class(self.Article).__table__.c
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
            history_class(self.Article).__table__.c
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
        cls = history_class(self.TextItem)
        manager = cls._sa_class_manager
        assert 'content' not in manager.keys()

    def test_versioning_with_column_exclusion(self):
        item = self.TextItem(name=u'Some textitem', content=u'Some content')
        self.session.add(item)
        self.session.commit()

        assert item.versions[0].name == u'Some textitem'
