import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy_continuum import (
    make_versioned
)


make_versioned()


class QueryPool(object):
    queries = []


@sa.event.listens_for(sa.engine.Engine, 'before_cursor_execute')
def log_sql(
    conn,
    cursor,
    statement,
    parameters,
    context,
    executemany
):
    QueryPool.queries.append(statement)


class TestCase(object):
    def setup_method(self, method):
        self.engine = create_engine(
            'postgres://postgres@localhost/sqlalchemy_continuum_test'
        )
        self.connection = self.engine.connect()
        #self.engine.echo = True
        self.Model = declarative_base()

        self.create_models()

        sa.orm.configure_mappers()
        if hasattr(self, 'Article'):
            self.ArticleHistory = self.Article.__versioned__['class']
        if hasattr(self, 'Tag'):
            self.TagHistory = self.Tag.__versioned__['class']
        self.create_tables()

        Session = sessionmaker(bind=self.connection)
        self.session = Session()

    def create_tables(self):
        self.Model.metadata.create_all(self.connection)

    def drop_tables(self):
        self.Model.metadata.drop_all(self.connection)

    def teardown_method(self, method):
        QueryPool.queries = []
        self.session.close_all()
        self.drop_tables()
        self.engine.dispose()
        self.connection.close()

    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        class Tag(self.Model):
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
