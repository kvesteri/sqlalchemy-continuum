import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy_continuum import (
    Versioned, versioned_session, configure_versioned
)


class TestCase(object):
    def setup_method(self, method):
        self.engine = create_engine(
            'postgres://postgres@localhost/sqlalchemy_versioned_test'
        )
        self.connection = self.engine.connect()
        #self.engine.echo = True
        self.Model = declarative_base()

        self.create_models()

        sa.event.listen(
            sa.orm.mapper, 'after_configured', configure_versioned
        )

        sa.orm.configure_mappers()
        self.ArticleHistory = self.Article.__versioned__['class']
        self.Model.metadata.create_all(self.connection)

        Session = sessionmaker(bind=self.connection)
        versioned_session(Session)
        self.session = Session()

    def teardown_method(self, method):
        self.session.close_all()
        self.Model.metadata.drop_all(self.connection)
        self.engine.dispose()
        self.connection.close()

    def create_models(self):
        class Article(self.Model, Versioned):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        class Tag(self.Model, Versioned):
            __tablename__ = 'tag'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(Article, backref='tags')

        self.Article = Article
        self.Tag = Tag
