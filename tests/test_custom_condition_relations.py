import sqlalchemy as sa
from sqlalchemy_versioned import Versioned
from tests import TestCase


class TestVersionedModel(TestCase):
    def create_models(self):
        class Article(self.Model, Versioned):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        class Tag(self.Model, Versioned):
            __tablename__ = 'tag'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            category = sa.Column(sa.Unicode(20))

        Article.primary_tags = sa.orm.relationship(
            Tag,
            primaryjoin=sa.and_(
                Tag.article_id == Article.id,
                Tag.category == 'primary'
            ),
        )

        Article.secondary_tags = sa.orm.relationship(
            Tag,
            primaryjoin=sa.and_(
                Tag.article_id == Article.id,
                Tag.category == 'secondary'
            ),
        )

        self.Article = Article
        self.Tag = Tag

    def test_relationship_primaryjoin(self):
        ArticleHistory = self.Article.__versioned__['class']
        assert str(ArticleHistory.primary_tags.property.primaryjoin) == (
            "tag_history.article_id = article_history.id AND "
            "tag_history.category = :category_1 AND tag_history.transaction_id"
            " = (SELECT max(tag_history.transaction_id) AS max_1 \n"
            "FROM tag_history, article_history \n"
            "WHERE tag_history.transaction_id <= "
            "article_history.transaction_id)"
        )
