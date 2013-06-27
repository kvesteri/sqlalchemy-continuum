import sqlalchemy as sa
from sqlalchemy_continuum import Versioned

from tests import TestCase


class TestReify(TestCase):
    def test_simple_reify(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()
        self.session.refresh(article)
        article.versions[0].reify()
        assert article.name == u'Some article'
        assert article.content == u'Some content'

    def test_reify_deleted_model(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)

        self.session.commit()
        old_article_id = article.id
        version = article.versions[0]
        self.session.delete(article)
        self.session.commit()
        version.reify()
        assert article.id == old_article_id
        assert article.name == u'Some article'
        assert article.content == u'Some content'

    def test_reify_deletion(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        old_article_id = article.id
        version = article.versions[0]
        self.session.delete(article)
        self.session.commit()
        version.reify()
        self.session.commit()
        version.next.reify()
        self.session.commit()
        assert not self.session.query(self.Article).get(old_article_id)

    def test_reify_version_with_one_to_many_relation(self):
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
        article.versions[0].reify()
        self.session.commit()

        assert article.name == u'Some article'
        assert article.content == u'Some content'
        assert len(article.tags) == 1
        assert article.tags[0].name == u'some tag'


class TestReifyManyToManyRelationship(TestCase):
    def create_models(self):
        class Article(self.Model, Versioned):
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

        class Tag(self.Model, Versioned):
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

    def test_reify_version_with_many_to_many_relation(self):
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
        article.versions[0].reify()
        self.session.commit()

        assert article.name == u'Some article'
        assert article.content == u'Some content'
        assert len(article.tags) == 1
        assert article.tags[0].name == u'some tag'
