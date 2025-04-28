from copy import copy
import os
import pathlib

import sqlmodel
from sqlmodel import Field, Relationship, Session
import sqlalchemy as sa
from sqlalchemy_continuum import make_versioned
from sqlalchemy_continuum import versioning_manager

from sqlalchemy_continuum.exc import ClassNotVersioned
from sqlalchemy_continuum.transaction import TransactionFactory
from sqlalchemy_continuum.utils import version_class
from tests import TestCase, get_driver_name, get_url_from_driver


models_path = pathlib.Path(__file__).parent.absolute() / "_models.py"


class SQLModelTestCase(TestCase):

    def setup_method(self, method):
        self.Model = sqlmodel.SQLModel
        make_versioned(user_cls=self.user_cls)

        driver = os.environ.get("DB", "sqlite")
        self.driver = get_driver_name(driver)
        versioning_manager.plugins = self.plugins
        versioning_manager.transaction_cls = TransactionFactory()
        versioning_manager.user_cls = self.user_cls

        self.engine = sa.create_engine(get_url_from_driver(self.driver), echo=True)
        # self.engine.echo = True
        self.create_models()
        sa.orm.configure_mappers()

        if hasattr(self, "Article"):
            try:
                self.ArticleVersion = version_class(self.Article)
            except ClassNotVersioned:
                pass
        if hasattr(self, "Tag"):
            try:
                self.TagVersion = version_class(self.Tag)
            except ClassNotVersioned:
                pass

        self.connection = self.engine.connect()
        self.session = Session(self.engine, autoflush=False)

        if driver == "postgres-native":
            self.session.execute(sa.text("CREATE EXTENSION IF NOT EXISTS hstore"))

        # Run any other custom SQL in here
        self.create_schema("other")
        self.session.commit()

        # Using an engine here instead of connection will call commit for us,
        # which lets us use the same syntax for 1.4 and 2.0
        self.Model.metadata.create_all(self.engine)

    def teardown_method(self, method):
        super().teardown_method(method)
        for entity in (
            "Article",
            "Tag",
            "ArticleVersion",
            "TagVersion",
            "User",
            "ArticleTagLink",
            "ArticleReferences",
        ):
            if hasattr(self, entity):
                self.Model.metadata.remove(getattr(self, entity).__table__)
        self.Model.metadata.clear()
        self.Model._sa_registry._class_registry.clear()

    def create_models(self):

        class Article(self.Model, table=True):
            __tablename__ = "article"
            __versioned__ = {}

            id: int = Field(sa_type=sa.Integer, primary_key=True)
            name: str = Field(sa_type=sa.Unicode(255), nullable=False)
            content: str = Field(sa_type=sa.UnicodeText)
            description: str = Field(
                sa_type=sa.UnicodeText, default=None, nullable=True
            )
            tags: list["Tag"] = Relationship(back_populates="article")

        class Tag(self.Model, table=True):
            __tablename__ = "tag"
            __versioned__ = {}

            id: int = Field(sa_type=sa.Integer, primary_key=True)
            name: str = Field(sa_type=sa.Unicode(255))
            article_id: int | None = Field(default=None, foreign_key="article.id")
            article: Article = Relationship(back_populates="tags")

        self.Article = Article
        self.Tag = Tag
