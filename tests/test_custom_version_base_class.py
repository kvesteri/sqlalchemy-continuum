import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


class TestCommonBaseClass(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        class ArticleVersionBase(self.Model):
            __abstract__ = True

        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (ArticleVersionBase, )
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

        self.TextItem = TextItem
        self.Article = Article
        self.ArticleVersionBase = ArticleVersionBase

    def test_each_class_has_distinct_translation_class(self):
        class_ = version_class(self.TextItem)
        assert class_.__name__ == 'TextItemVersion'
        class_ = version_class(self.Article)
        assert class_.__name__ == 'ArticleVersion'
        assert issubclass(class_, self.ArticleVersionBase)
