import sqlalchemy as sa
from sqlalchemy_i18n import Translatable, make_translatable
from . import TestCase


make_translatable()


class TestVersioningWithI18nExtension(TestCase):
    def create_models(self):
        class Versioned(self.Model):
            __abstract__ = True
            __versioned__ = {
                'base_classes': (self.Model, )
            }

        class Article(self.Model, Translatable):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
            __translatable__ = {
                'base_classes': (Versioned, )
            }
            __translated_columns__ = [
                sa.Column('name', sa.Unicode(255)),
                sa.Column('content', sa.UnicodeText)
            ]

            def get_locale(self):
                return 'en'

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            description = sa.Column(sa.UnicodeText)

        self.Article = Article

    def test_changeset(self):
        article = self.Article()
        article.name = u'Some article'
        self.session.add(article)
        self.session.commit()

        assert article.translations['en'].versions[0].changeset
