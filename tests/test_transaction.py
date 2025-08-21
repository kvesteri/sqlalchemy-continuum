import sqlalchemy as sa

from sqlalchemy_continuum import versioning_manager
from sqlalchemy_continuum.plugins import TransactionMetaPlugin
from tests import TestCase


class TestTransaction(TestCase):
    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.article = self.Article()
        self.article.name = 'Some article'
        self.article.content = 'Some content'
        self.article.tags.append(self.Tag(name='Some tag'))
        self.session.add(self.article)
        self.session.commit()

    def test_relationships(self):
        assert self.article.versions[0].transaction

    def test_only_saves_transaction_if_actual_modifications(self):
        self.article.name = 'Some article'
        self.session.commit()
        self.article.name = 'Some article'
        self.session.commit()
        assert self.session.query(versioning_manager.transaction_cls).count() == 1

    def test_repr(self):
        transaction = self.session.query(versioning_manager.transaction_cls).first()
        assert (
            f'<Transaction id={transaction.id}, issued_at={transaction.issued_at!r}>'
            == repr(transaction)
        )

    def test_changed_entities(self):
        article_v0 = self.article.versions[0]
        transaction = article_v0.transaction
        assert transaction.changed_entities == {
            self.ArticleVersion: [article_v0],
            self.TagVersion: [self.article.tags[0].versions[0]],
        }


# Check that the tests pass without TransactionChangesPlugin
class TestTransactionWithoutChangesPlugin(TestTransaction):
    plugins = [TransactionMetaPlugin()]


class TestAssigningUserClass(TestCase):
    user_cls = 'User'

    def create_models(self):
        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = {'base_classes': (self.Model,)}

            id = sa.Column(sa.Unicode(255), primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)

        self.User = User

    def test_copies_primary_key_type_from_user_class(self):
        attr = versioning_manager.transaction_cls.user_id
        assert isinstance(attr.property.columns[0].type, sa.Unicode)


class TestAssigningUserClassInOtherSchema(TestCase):
    user_cls = 'User'

    def create_models(self):
        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = {'base_classes': (self.Model,)}
            __table_args__ = {'schema': 'other'}

            id = sa.Column(sa.Unicode(255), primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)

        self.User = User

    def test_can_build_transaction_model(self):
        # If create_models didn't crash this should be good
        pass
