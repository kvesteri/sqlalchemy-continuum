from datetime import datetime
import sqlalchemy as sa
from sqlalchemy_continuum import is_modified

from tests import TestCase


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
