from sqlmodel import Field, Relationship
from tests.sqlmodel import SQLModelTestCase
import sqlalchemy as sa


class TestRelationshipToNonVersionedClass(SQLModelTestCase):
    def create_models(self):
        class User(self.Model, table=True):
            __tablename__ = 'user'

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
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()

        assert isinstance(article.versions[0].author, self.User)

    def test_change_relationship(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        user = self.User(name=u'Some user')
        self.session.add(article)
        self.session.add(user)
        self.session.commit()

        assert article.versions.count() == 1
        article.author = user
        self.session.commit()
        assert article.versions.count() == 2


class TestManyToManyRelationshipToNonVersionedClass(SQLModelTestCase):
    def create_models(self):

        class ArticleTagLink(self.Model, table=True):
            __tablename__ = "article_tag"
            article_id: int | None = Field(
                default=None, foreign_key="article.id", primary_key=True
            )
            tag_id: int | None = Field(
                default=None, foreign_key="tag.id", primary_key=True
            )

        class Article(self.Model, table=True):
            __tablename__ = "article"
            __versioned__ = {}

            id: int | None = Field(default=None, primary_key=True)
            name: str = Field(max_length=255)
            content: str = Field(default="")
            tags: list["Tag"] = Relationship(
                back_populates="articles", link_model=ArticleTagLink
            )

        class Tag(self.Model, table=True):
            __tablename__ = "tag"

            id: int | None = Field(default=None, primary_key=True)
            name: str = Field(max_length=255)
            articles: list[Article] = Relationship(
                back_populates="tags", link_model=ArticleTagLink
            )

        self.Article = Article
        self.Tag = Tag
        self.ArticleTagLink = ArticleTagLink


    def test_single_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        assert len(article.versions[0].tags) == 1
        assert isinstance(article.versions[0].tags[0], self.Tag)
