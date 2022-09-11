import copy
import datetime
import sqlalchemy as sa
from sqlalchemy_continuum.utils import parent_table, version_table

from tests import TestCase


class TestParentTable(TestCase):

    def create_models(self):
        super().create_models()

        article_author_table = sa.Table(
            'article_author',
            self.Model.metadata,
            sa.Column('article_id', sa.Integer, sa.ForeignKey('article.id'), primary_key=True, nullable=False),
            sa.Column('author_id', sa.Integer, sa.ForeignKey('author.id'), primary_key=True, nullable=False),
            sa.Column('created_date', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp(), default=datetime.datetime.utcnow),
        )
       
        class Author(self.Model):
            __tablename__ = 'author'
            __versioned__ = {
                'baseclass': (self.Model, )
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            articles = sa.orm.relationship('Article', secondary=article_author_table, backref='author')


        self.Author = Author
        self.article_author_table = article_author_table

    def test_parent_table_from_version_table(self):
        author_version_table = version_table(self.Author.__table__)
        assert parent_table(author_version_table) == self.Author.__table__

    def test_parent_table_from_association_table(self):
        versioned_article_author_table = version_table(self.article_author_table)
        assert parent_table(versioned_article_author_table) == self.article_author_table