import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


class TestCommonBaseClass(TestCase):
    def create_models(self):
        class Versioned(object):
            __versioned__ = {
                'base_classes': (self.Model, )
            }

        class TextItem(self.Model, Versioned):
            __tablename__ = 'text_item'

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        class Article(self.Model, Versioned):
            __tablename__ = 'article'
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.TextItem = TextItem
        self.Article = Article

    def test_each_class_has_distinct_translation_class(self):
        class_ = version_class(self.TextItem)
        assert class_.__name__ == 'TextItemVersion'
        class_ = version_class(self.Article)
        assert class_.__name__ == 'ArticleVersion'
