import sqlalchemy as sa

from tests import TestCase


class TestRevertOneToOneSecondaryRelationship(TestCase):
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

        Tag.article = sa.orm.relationship(
            Article,
            secondary=article_tag,
            backref=sa.orm.backref(
                'tag',
                uselist=False
            ),
            uselist=False
        )

        self.Article = Article
        self.Tag = Tag

    def test_revert_relationship(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tag = tag
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tag == tag.versions[0]
        article.tag = None
        self.session.commit()
        self.session.refresh(article)
        assert article.tag is None
        article.versions[0].revert(relations=['tag'])
        self.session.commit()

        assert article.tag == tag
        assert article.tag.name == u'some tag'
