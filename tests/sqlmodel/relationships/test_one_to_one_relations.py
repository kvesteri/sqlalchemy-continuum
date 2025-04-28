from sqlmodel import Field, Relationship
from tests import create_test_cases
from tests.sqlmodel import SQLModelTestCase
import sqlalchemy as sa


class OneToOneRelationshipsTestCase(SQLModelTestCase):
    def create_models(self):
        class User(self.Model, table=True):
            __tablename__ = 'user'
            __versioned__ = {}

            id: int | None = Field(sa_type=sa.Integer, default=None, primary_key=True)
            name: str = Field(sa_type=sa.Unicode(255))
            articles: list["Article"] = Relationship(back_populates="author")

        class Article(self.Model, table=True):
            __tablename__ = 'article'
            __versioned__ = {}

            id: int | None = Field(default=None, primary_key=True)
            name: str = Field(sa_type=sa.Unicode(255), nullable=False)
            content: str = Field(sa_type=sa.UnicodeText)
            description: str = Field(sa_type=sa.UnicodeText, default="")
            author_id: int | None = Field(sa_type=sa.Integer, foreign_key="user.id")
            author: User = Relationship(back_populates="articles")

        self.Article = Article
        self.User = User

    def test_single_insert(self):
        article = self.Article(name=u'Some article', content=u'Some content')
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()

        assert article.versions[0].author

    def test_multiple_relation_versions(self):
        article = self.Article(name=u'Some article', content=u'Some content')
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()
        user.name = u'Someone else'
        self.session.commit()

        assert article.versions[0].author == user.versions[0]

    def test_multiple_consecutive_inserts_and_removes(self):
        article = self.Article(name=u'Some article', content=u'Some content')
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()
        user.name = u'Someone else'
        self.session.commit()

        article.name = u'Updated article'

        article2 = self.Article(
            name=u'Article 2',
            content=""
        )
        self.session.add(article2)
        article2.author = user
        self.session.commit()

        assert article2.versions[0].author == user.versions[1]

    def test_replace(self):
        article = self.Article(name=u'Some article', content=u'Some content')
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()
        other_user = self.User(name=u'Some other user')
        article.author = other_user
        self.session.commit()

        assert article.versions[1].author == other_user.versions[0]


create_test_cases(OneToOneRelationshipsTestCase)
