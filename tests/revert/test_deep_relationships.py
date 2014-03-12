import sqlalchemy as sa

from tests import TestCase


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
        assert len(article.versions[0].tags) == 1
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
