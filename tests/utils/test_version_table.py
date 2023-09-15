import pytest
import datetime
import sqlalchemy as sa
from tests import TestCase, uses_native_versioning

from sqlalchemy_continuum.utils import version_table

class TestVersionTableDefault(TestCase):

    def create_models(self):
        super().create_models()

        article_author_table = sa.Table(
            'article_author',
            self.Model.metadata,
            sa.Column('article_id', sa.Integer, sa.ForeignKey('article.id'), primary_key=True, nullable=False),
            sa.Column('author_id', sa.Integer, sa.ForeignKey('author.id'), primary_key=True, nullable=False),
            sa.Column('created_date', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp(), default=datetime.datetime.utcnow),
        )

        user_activity_table = sa.Table(
            'user_activity',
            self.Model.metadata,
            sa.Column('user_id', sa.INTEGER, sa.ForeignKey('user.id'), nullable=False),
            sa.Column('login_time', sa.DateTime, nullable=False),
            sa.Column('logout_time', sa.DateTime, nullable=False)
        )
        class Author(self.Model):
            __tablename__ = 'author'
            __versioned__ = {
                'table_name': '%s_custom'
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            articles = sa.orm.relationship('Article', secondary=article_author_table, backref='author')

        class User(self.Model):
            __tablename__ = 'user'

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        self.User = User
        self.Author = Author
        self.article_author_table = article_author_table
        self.user_activity_table = user_activity_table

    def test_version_table_with_model(self):
        ArticleVersionTableName = version_table(self.Article.__table__)
        assert ArticleVersionTableName.fullname == 'article_version'

    def test_version_table_with_association_table(self):
        ArticleAuthorVersionedTableName = version_table(self.article_author_table)
        assert ArticleAuthorVersionedTableName.fullname == 'article_author_version'

    def test_version_table_with_model_version_attr(self):
        AuthorVersionedTableName = version_table(self.Author.__table__)
        assert AuthorVersionedTableName.fullname == 'author_custom'

    def test_version_table_with_non_version_model(self):
        with pytest.raises(KeyError):
            version_table(self.User.__table__)
    
    def test_version_table_with_non_version_table(self):
        with pytest.raises(KeyError):
            version_table(self.user_activity_table)
        
class TestVersionTableUserDefined(TestVersionTableDefault):


    @property
    def options(self):
        return {
            'create_models': self.should_create_models,
            'native_versioning': uses_native_versioning(),
            'base_classes': (self.Model, ),
            'strategy': self.versioning_strategy,
            'transaction_column_name': self.transaction_column_name,
            'end_transaction_column_name': self.end_transaction_column_name,
            'table_name': '%s_user_defined'
        }

    def test_version_table_with_model(self):
        ArticleVersionTableName = version_table(self.Article.__table__)
        assert ArticleVersionTableName.fullname == 'article_user_defined'

    def test_version_table_with_association_table(self):
        ArticleAuthorVersionedTableName = version_table(self.article_author_table)
        assert ArticleAuthorVersionedTableName.fullname == 'article_author_user_defined'

