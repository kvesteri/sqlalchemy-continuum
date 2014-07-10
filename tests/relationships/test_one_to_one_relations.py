from copy import copy
from tests import TestCase, create_test_cases
import sqlalchemy as sa


class OneToOneRelationshipsTestCase(TestCase):
    def create_models(self):
        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = copy(self.options)

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)
            author_id = sa.Column(sa.Integer, sa.ForeignKey(User.id))
            author = sa.orm.relationship(User)

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

        assert article.versions[0].author

    def test_multiple_relation_versions(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()
        user.name = u'Someone else'
        self.session.commit()

        assert article.versions[0].author == user.versions[0]

    def test_multiple_consecutive_inserts_and_removes(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()
        user.name = u'Someone else'
        self.session.commit()

        article.name = u'Updated article'

        article2 = self.Article(
            name=u'Article 2'
        )
        self.session.add(article2)
        article2.author = user
        self.session.commit()

        assert article2.versions[0].author == user.versions[1]

    def test_replace(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        user = self.User(name=u'Some user')
        article.author = user
        self.session.add(article)
        self.session.commit()
        other_user = self.User(name=u'Some other user')
        article.author = other_user
        self.session.commit()

        assert article.versions[1].author == other_user.versions[0]


create_test_cases(OneToOneRelationshipsTestCase)
