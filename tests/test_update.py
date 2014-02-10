import sqlalchemy as sa
from tests import TestCase


class TestUpdate(TestCase):
    def test_creates_versions_on_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'

        self.session.commit()
        self.session.refresh(article)
        version = article.versions.all()[-1]
        assert version.name == u'Updated name'
        assert version.content == u'Updated content'
        assert version.transaction.id == version.transaction_id

    def test_partial_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.content = u'Updated content'

        self.session.commit()
        self.session.refresh(article)
        version = article.versions.all()[-1]
        assert version.name == u'Some article'
        assert version.content == u'Updated content'
        assert version.transaction.id == version.transaction_id

    def test_update_with_same_values(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        self.session.refresh(article)
        article.name = u'Some article'

        self.session.commit()
        assert article.versions.count() == 1

    def test_stores_operation_type(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Some other article'

        self.session.commit()
        assert article.versions[-1].operation_type == 1

    def test_multiple_updates_within_same_transaction(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.content = u'Updated content'
        self.session.flush()
        article.content = u'Updated content 2'
        self.session.commit()
        assert article.versions.count() == 2
        version = article.versions.all()[-1]
        assert version.name == u'Some article'
        assert version.content == u'Updated content 2'


class TestUpdateWithDefaultValues(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            updated_at = sa.Column(sa.DateTime, default=sa.func.now())
            is_editable = sa.Column(sa.Boolean)

        self.Article = Article

    def test_update_with_default_values(self):
        article = self.Article()
        article.name = u'Some article'
        article.is_editable = False
        self.session.add(article)
        self.session.commit()

        article.is_editable = True
        self.session.commit()
        article = article.versions.all()[-1]
        assert article.name == u'Some article'
