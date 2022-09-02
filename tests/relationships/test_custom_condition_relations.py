import sqlalchemy as sa
from tests import TestCase, create_test_cases
from packaging import version as py_pkg_version

class CustomConditionRelationsTestCase(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
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
            category = sa.Column(sa.Unicode(20))

        if py_pkg_version.parse(sa.__version__) < py_pkg_version.parse('1.4.0'):
            primary_key_overlaps = {}
            secondary_key_overlaps = {}
        else:
            primary_key_overlaps = {'overlaps': 'secondary_tags, Article'}
            secondary_key_overlaps = {'overlaps': 'primary_tags, Article'}
        Article.primary_tags = sa.orm.relationship(
            Tag,
            primaryjoin=sa.and_(
                Tag.article_id == Article.id,
                Tag.category == u'primary'
            ),
            **primary_key_overlaps
        )

        Article.secondary_tags = sa.orm.relationship(
            Tag,
            primaryjoin=sa.and_(
                Tag.article_id == Article.id,
                Tag.category == u'secondary'
            ),
            **secondary_key_overlaps
        )

        self.Article = Article
        self.Tag = Tag

    def test_relationship_condition_reflection(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.primary_tags.append(
            self.Tag(name=u'tag #1', category=u'primary')
        )
        article.secondary_tags.append(
            self.Tag(name=u'tag #2', category=u'secondary')
        )
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].primary_tags
        assert article.versions[0].secondary_tags


create_test_cases(CustomConditionRelationsTestCase)
