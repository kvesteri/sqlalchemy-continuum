import sqlalchemy as sa
from sqlalchemy_i18n import Translatable, make_translatable, translation_base
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
                'locales': ['fi', 'en']
            }
            locale = 'en'

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            description = sa.Column(sa.UnicodeText)

        class ArticleTranslation(translation_base(Article)):
            __tablename__ = 'article_translation'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
            name = sa.Column('name', sa.Unicode(255))
            content = sa.Column('content', sa.UnicodeText)

        self.Article = Article

    def test_changeset(self):
        article = self.Article()
        article.name = u'Some article'
        self.session.add(article)
        self.session.commit()

        assert article.translations['en'].versions[0].changeset

    def test_changed_entities(self):
        article = self.Article()
        article.description = u'something'
        self.session.add(article)
        self.session.commit()
        article.name = u'Some article'
        self.session.commit()

        tx_log = self.Article.__versioned__['transaction_log']
        tx = (
            self.session.query(tx_log)
            .order_by(sa.desc(tx_log.id))
            .first()
        )
        assert 'ArticleTranslation' in tx.entity_names

    def test_history_with_many_translations(self):
        self.article = self.Article()
        self.article.description = u'Some text'
        self.session.add(self.article)

        with self.article.force_locale('fi'):
            self.article.name = u'Text 1'
        with self.article.force_locale('en'):
            self.article.name = u'Text 2'

        self.session.commit()

        TransactionLog = self.Article.__versioned__['transaction_log']
        transaction = self.session.query(TransactionLog).one()

        assert transaction.changes[1].entity_name == u'ArticleTranslation'
