from pytest import raises

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy_continuum import changeset
from sqlalchemy_continuum.utils import (
    get_bind,
    is_modified,
    parent_class,
    tx_column_name,
    version_class,
)

from tests import TestCase, create_test_cases


class TestChangeSet(TestCase):
    def test_changeset_for_new_value(self):
        article = self.Article(name=u'Some article')
        assert changeset(article) == {'name': [u'Some article', None]}

    def test_changeset_for_deletion(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.commit()
        self.session.delete(article)
        assert changeset(article) == {'name': [None, u'Some article']}

    def test_changeset_for_update(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.commit()
        article.tags
        article.name = u'Updated article'
        assert changeset(article) == {
            'name': [u'Updated article', u'Some article']
        }


class TestIsModified(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'exclude': 'content'
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            created_at = sa.Column(sa.DateTime, default=datetime.now)
            content = sa.Column(sa.Unicode(255))

        self.Article = Article

    def test_included_column(self):
        article = self.Article(name=u'Some article')
        assert is_modified(article)

    def test_excluded_column(self):
        article = self.Article(content=u'Some content')
        assert not is_modified(article)

    def test_auto_assigned_datetime_exclusion(self):
        article = self.Article(created_at=datetime.now())
        assert not is_modified(article)


class TestVersionClass(TestCase):
    def test_version_class_for_versioned_class(self):
        ArticleVersion = version_class(self.Article)
        assert ArticleVersion.__name__ == 'ArticleVersion'

    def test_throws_error_for_non_versioned_class(self):
        with raises(KeyError):
            parent_class(self.Article)


class TestGetBind(TestCase):
    def test_with_session(self):
        assert get_bind(self.session) == self.connection

    def test_with_connection(self):
        assert get_bind(self.connection) == self.connection

    def test_with_model_object(self):
        article = self.Article()
        self.session.add(article)
        assert get_bind(article) == self.connection

    def test_with_unknown_type(self):
        with raises(TypeError):
            get_bind(None)


class TestParentClass(TestCase):
    def test_parent_class_for_version_class(self):
        ArticleVersion = version_class(self.Article)
        assert parent_class(ArticleVersion) == self.Article

    def test_throws_error_for_non_version_class(self):
        with raises(KeyError):
            parent_class(self.Article)


setting_variants = {
    'transaction_column_name': ['transaction_id', 'tx_id'],
}


class TxColumnNameTestCase(TestCase):
    def test_with_version_class(self):
        assert tx_column_name(version_class(self.Article)) == self.options[
            'transaction_column_name'
        ]

    def test_with_version_obj(self):
        history_obj = version_class(self.Article)()
        assert tx_column_name(history_obj) == self.options[
            'transaction_column_name'
        ]

    def test_with_versioned_class(self):
        assert tx_column_name(self.Article) == self.options[
            'transaction_column_name'
        ]


create_test_cases(TxColumnNameTestCase, setting_variants=setting_variants)
