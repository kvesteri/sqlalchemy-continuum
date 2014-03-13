from copy import copy
import sqlalchemy as sa
from sqlalchemy_continuum.utils import tx_column_name
from tests import TestCase, create_test_cases


class VersionModelAccessorsTestCase(TestCase):
    def test_previous_for_first_version(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        assert not article.versions[0].previous

    def test_previous_for_live_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()
        version = article.versions[1]

        assert version.previous.name == u'Some article'
        assert (
            getattr(version.previous, tx_column_name(version)) ==
            getattr(version, tx_column_name(version)) - 1
        )

    def test_previous_for_deleted_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        self.session.delete(article)
        self.session.commit()
        versions = (
            self.session.query(self.ArticleVersion)
            .order_by(
                getattr(
                    self.ArticleVersion,
                    self.options['transaction_column_name']
                )
            )
        ).all()
        assert versions[1].previous.name == u'Some article'

    def test_previous_chaining(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated article'
        self.session.commit()
        self.session.delete(article)
        self.session.commit()
        version = (
            self.session.query(self.ArticleVersion)
            .order_by(
                getattr(
                    self.ArticleVersion,
                    self.options['transaction_column_name']
                )
            )
        ).all()[-1]
        assert version.previous.previous

    def test_previous_two_versions(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        article2 = self.Article()
        article2.name = u'Second article'
        article2.content = u'Second article'
        self.session.add(article2)
        self.session.commit()

        article.name = u'Updated article'
        self.session.commit()
        article.name = u'Updated article 2'
        self.session.commit()

        assert article.versions[2].previous
        assert article.versions[1].previous
        assert article.versions[2].previous == article.versions[1]
        assert article.versions[1].previous == article.versions[0]

    def test_next_two_versions(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        article2 = self.Article()
        article2.name = u'Second article'
        article2.content = u'Second article'
        self.session.add(article2)
        self.session.commit()

        article.name = u'Updated article'
        self.session.commit()
        article.name = u'Updated article 2'
        self.session.commit()

        assert article.versions[0].next
        assert article.versions[1].next
        assert article.versions[0].next == article.versions[1]
        assert article.versions[1].next == article.versions[2]

    def test_next_for_last_version(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        assert not article.versions[0].next

    def test_next_for_live_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()
        version = article.versions[0]

        assert version.next.name == u'Updated name'

    def test_next_for_deleted_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        version = article.versions[0]
        self.session.delete(article)
        self.session.commit()

        assert version.next

    def test_chaining_next(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated article'
        self.session.commit()
        article.content = u'Updated content'
        self.session.commit()

        versions = article.versions.all()
        version = versions[0]
        assert version.next == versions[1]
        assert version.next.next == versions[2]

    def test_index_for_deleted_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        self.session.delete(article)
        self.session.commit()

        versions = (
            self.session.query(self.ArticleVersion)
            .order_by(
                getattr(
                    self.ArticleVersion,
                    self.options['transaction_column_name']
                )
            )
        ).all()
        assert versions[0].index == 0
        assert versions[1].index == 1

    def test_index_for_live_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        assert article.versions[0].index == 0


class VersionModelAccessorsWithCompositePkTestCase(TestCase):
    def create_models(self):
        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = copy(self.options)

            first_name = sa.Column(sa.Unicode(255), primary_key=True)
            last_name = sa.Column(sa.Unicode(255), primary_key=True)
            email = sa.Column(sa.Unicode(255))

        self.User = User

    def test_previous_two_versions(self):
        user = self.User(
            first_name=u'Some user',
            last_name=u'Some last_name',
        )
        self.session.add(user)
        self.session.commit()
        user2 = self.User(
            first_name=u'Second user',
            last_name=u'Second user',
        )
        self.session.add(user2)
        self.session.commit()

        user.email = u'Updated email'
        self.session.commit()
        user.email = u'Updated email 2'
        self.session.commit()

        assert user.versions[2].previous
        assert user.versions[1].previous
        assert user.versions[2].previous == user.versions[1]
        assert user.versions[1].previous == user.versions[0]

    def test_next_two_versions(self):
        user = self.User()
        user.first_name = u'Some user'
        user.last_name = u'Some last_name'
        self.session.add(user)
        self.session.commit()
        user2 = self.User()
        user2.first_name = u'Second user'
        user2.last_name = u'Second user'
        self.session.add(user2)
        self.session.commit()

        user.email = u'Updated user'
        self.session.commit()
        user.email = u'Updated user 2'
        self.session.commit()

        assert user.versions[0].next
        assert user.versions[1].next
        assert user.versions[0].next == user.versions[1]
        assert user.versions[1].next == user.versions[2]


create_test_cases(VersionModelAccessorsTestCase)
create_test_cases(VersionModelAccessorsWithCompositePkTestCase)
