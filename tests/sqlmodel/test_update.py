from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel
from tests.sqlmodel import SQLModelTestCase


class TestUpdateSQLModel(SQLModelTestCase):
    def test_creates_versions_on_update(self):
        article = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'

        self.session.commit()
        self.session.refresh(article)
        version = list(article.versions)[-1]
        assert version.name == u'Updated name'
        assert version.content == u'Updated content'
        assert version.transaction.id == version.transaction_id

    def test_partial_update(self):
        article = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article)
        self.session.commit()

        article.content = u'Updated content'

        self.session.commit()
        self.session.refresh(article)
        version = list(article.versions)[-1]
        assert version.name == u'Some article'
        assert version.content == u'Updated content'
        assert version.transaction.id == version.transaction_id

    def test_update_with_same_values(self):
        article = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article)
        self.session.commit()
        self.session.refresh(article)
        article.name = u'Some article'

        self.session.commit()
        assert article.versions.count() == 1

    def test_stores_operation_type(self):
        article = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article)
        self.session.commit()

        article.name = u'Some other article'

        self.session.commit()
        assert list(article.versions)[-1].operation_type == 1

    def test_multiple_updates_within_same_transaction(self):
        article = self.Article(name=u"Some article", content=u"Some content")
        self.session.add(article)
        self.session.commit()

        article.content = u'Updated content'
        self.session.flush()
        article.content = u'Updated content 2'
        self.session.commit()
        assert article.versions.count() == 2
        version = list(article.versions)[-1]
        assert version.name == u'Some article'
        assert version.content == u'Updated content 2'


class TestUpdateWithDefaultValuesSQLModel(SQLModelTestCase):
    def create_models(self):
        self.Model = SQLModel
        class Article(self.Model, table=True):
            __tablename__ = 'article'
            __versioned__ = {
            }
            id: int | None = Field(default=None, primary_key=True)
            name: str = Field(sa_type=sa.Unicode(255), nullable=False)
            updated_at: datetime = Field(sa_type=sa.DateTime, sa_column_kwargs={"server_default": sa.func.now()})
            is_editable: bool = Field()

        self.Article = Article

    def test_update_with_default_values(self):
        article = self.Article(name=u"Some article", is_editable=False)
        self.session.add(article)
        self.session.commit()

        article.is_editable = True
        self.session.commit()
        article = list(article.versions)[-1]
        assert article.name == u'Some article'
