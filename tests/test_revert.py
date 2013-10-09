from pytest import raises
import sqlalchemy as sa
from sqlalchemy_continuum.reverter import Reverter, ReverterException

from tests import TestCase


class TestReverter(TestCase):
    def test_raises_exception_for_unknown_relations(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)

        self.session.commit()
        version = article.versions[0]

        with raises(ReverterException):
            Reverter(version, relations=['unknown_relation'])


class RevertTestCase(TestCase):
    def add_article(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        return article

    def test_simple_revert(self):
        article = self.add_article()
        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()
        self.session.refresh(article)
        article.versions[0].revert()
        assert article.name == u'Some article'
        assert article.content == u'Some content'

    def test_revert_deleted_model(self):
        article = self.add_article()
        old_article_id = article.id
        version = article.versions[0]
        self.session.delete(article)
        self.session.commit()
        version.revert()
        assert article.id == old_article_id
        assert article.name == u'Some article'
        assert article.content == u'Some content'

    def test_revert_deletion(self):
        article = self.add_article()
        old_article_id = article.id
        version = article.versions[0]
        self.session.delete(article)
        self.session.commit()
        version.revert()
        self.session.commit()
        assert self.session.query(self.Article).count() == 1
        article = self.session.query(self.Article).get(old_article_id)

        assert version.next.next

        version.next.revert()
        self.session.commit()
        assert not self.session.query(self.Article).get(old_article_id)

    def test_revert_version_with_one_to_many_relation(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated name'
        article.content = u'Updated content'
        article.tags = []
        self.session.commit()
        self.session.refresh(article)
        assert article.tags == []
        assert len(article.versions[0].tags.all()) == 1
        assert article.versions[0].tags[0].article
        article.versions[0].revert(relations=['tags'])
        self.session.commit()

        assert article.name == u'Some article'
        assert article.content == u'Some content'
        assert len(article.tags) == 1
        assert article.tags[0].name == u'some tag'


class TestRevertWithDefaultVersioningStrategy(RevertTestCase):
    pass


class TestRevertWithValidityVersioningStrategy(RevertTestCase):
    versioning_strategy = 'validity'


class TestRevertWithCustomTransactionColumn(RevertTestCase):
    transaction_column_name = 'tx_id'


class TestRevertWithColumnExclusion(RevertTestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'exclude': ['description']
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        self.Article = Article

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(Article, backref='tags')

        self.Article = Article
        self.Tag = Tag


class TestRevertManyToManyRelationship(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        article_tag = sa.Table(
            'article_tag',
            self.Model.metadata,
            sa.Column(
                'article_id',
                sa.Integer,
                sa.ForeignKey('article.id', ondelete='CASCADE'),
                primary_key=True,
            ),
            sa.Column(
                'tag_id',
                sa.Integer,
                sa.ForeignKey('tag.id', ondelete='CASCADE'),
                primary_key=True
            )
        )

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        Tag.articles = sa.orm.relationship(
            Article,
            secondary=article_tag,
            backref='tags'
        )

        self.Article = Article
        self.Tag = Tag

    def test_revert_version_with_many_to_many_relation(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tags.count() == 1
        article.tags.remove(tag)
        self.session.commit()
        self.session.refresh(article)
        assert article.tags == []
        article.versions[0].revert(relations=['tags'])
        self.session.commit()

        assert article.name == u'Some article'
        assert article.content == u'Some content'
        assert len(article.tags) == 1
        assert article.tags[0].name == u'some tag'


class TestRevertDeepRelations(TestCase):
    def create_models(self):
        class Category(self.Model):
            __tablename__ = 'category'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            category_id = sa.Column(sa.Integer, sa.ForeignKey(Category.id))
            category = sa.orm.relationship(Category, backref='articles')

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(Article, backref='tags')

        self.Category = Category
        self.Article = Article
        self.Tag = Tag

    def test_revert_deep_relationships(self):
        category = self.Category()
        category.name = u'Some category'

        article = self.Article(
            name=u'Some article',
        )
        category.articles.append(article)
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tags.count() == 1
        article.tags.remove(tag)
        category.articles.remove(article)
        self.session.commit()
        self.session.refresh(article)
        assert article.tags == []
        category.versions[0].revert(relations=['articles', 'articles.tags'])
        self.session.commit()

        self.session.refresh(category)
        article = category.articles[0]

        assert article.name == u'Some article'
        assert len(article.tags) == 1
        assert article.tags[0].name == u'some tag'
