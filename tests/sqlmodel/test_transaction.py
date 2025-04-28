import sqlalchemy as sa
from sqlmodel import AutoString, Field
from sqlalchemy_continuum import versioning_manager
from tests.sqlmodel import SQLModelTestCase
from sqlalchemy_continuum.plugins import TransactionMetaPlugin



class TestTransaction(SQLModelTestCase):
    def setup_method(self, method):
        SQLModelTestCase.setup_method(self, method)
        self.article = self.Article(name= u'Some article', content=u'Some content')
        self.article.tags.append(self.Tag(name=u'Some tag'))
        self.session.add(self.article)
        self.session.commit()

    def test_relationships(self):
        assert self.article.versions[0].transaction

    def test_only_saves_transaction_if_actual_modifications(self):
        self.article.name = u'Some article'
        self.session.commit()
        self.article.name = u'Some article'
        self.session.commit()
        assert self.session.query(
            versioning_manager.transaction_cls
        ).count() == 1

    def test_repr(self):
        transaction = self.session.query(
            versioning_manager.transaction_cls
        ).first()
        assert (
            '<Transaction id=%d, issued_at=%r>' % (
                transaction.id,
                transaction.issued_at
            ) ==
            repr(transaction)
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


class TestAssigningUserClass(SQLModelTestCase):
    user_cls = 'User'

    def create_models(self):
        class User(self.Model, table=True):
            __tablename__ = 'user'
            __versioned__ = {}
            id: str | None = Field(default=None, primary_key=True)
            name: str = Field(sa_type=sa.Unicode(255), nullable=False)

        self.User = User

    def test_copies_primary_key_type_from_user_class(self):
        attr = versioning_manager.transaction_cls.user_id
        assert isinstance(attr.property.columns[0].type, AutoString)


class TestAssigningUserClassInOtherSchema(SQLModelTestCase):
    user_cls = 'User'

    def create_models(self):
        class User(self.Model, table=True):
            __tablename__ = 'user'
            __versioned__ = {}
            __table_args__ = {'schema': 'other'}

            id: int | None = Field(default=None, primary_key=True)
            name: str = Field(sa_type=sa.Unicode(255), nullable=False)

        self.User = User

    def test_can_build_transaction_model(self):
        # If create_models didn't crash this should be good
        pass

