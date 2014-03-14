import sqlalchemy as sa

from tests import TestCase


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

    def test_revert_remove(self):
        article = self.Article()
        article.name = u'Some article'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        assert len(article.versions[0].tags) == 1
        article.tags.remove(tag)
        self.session.commit()
        self.session.refresh(article)
        assert article.tags == []
        article.versions[0].revert(relations=['tags'])
        self.session.commit()

        assert article.name == u'Some article'
        assert len(article.tags) == 1
        assert article.tags[0].name == u'some tag'

    def test_revert_remove_with_multiple_parents(self):
        article = self.Article(name=u'Some article')
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        article2 = self.Article(name=u'Some article')
        tag2 = self.Tag(name=u'some tag')
        article2.tags.append(tag2)
        self.session.add(article2)
        self.session.commit()
        article.tags.remove(tag)
        self.session.commit()
        self.session.refresh(article)

        assert len(article.tags) == 0
        article.versions[0].revert(relations=['tags'])
        self.session.commit()

        assert article.name == u'Some article'
        assert len(article.tags) == 1
        assert article.tags[0].name == u'some tag'
