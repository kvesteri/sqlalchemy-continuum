import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


class JoinTableInheritanceWithRelationshipTestCase(TestCase):
    def create_models(self):

        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'base_classes': (self.Model, )
            }
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

            author_id = sa.Column(sa.Integer, sa.ForeignKey(User.id))
            author = sa.orm.relationship(User)

            discriminator = sa.Column(
                sa.Unicode(100)
            )

            __mapper_args__ = {
                'polymorphic_on': discriminator,
                'with_polymorphic': '*'
            }

        class Article(TextItem):
            __tablename__ = 'article'
            __mapper_args__ = {'polymorphic_identity': u'article'}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(TextItem.id),
                autoincrement=True, primary_key=True
            )

        class BlogPost(TextItem):
            __tablename__ = 'blog_post'
            __mapper_args__ = {'polymorphic_identity': u'blog_post'}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(TextItem.id),
                autoincrement=True, primary_key=True
            )

        self.TextItem = TextItem
        self.Article = Article
        self.BlogPost = BlogPost
        self.User = User

    def setup_method(self, method):
        TestCase.setup_method(self, method)
        self.TextItemVersion = version_class(self.TextItem)
        self.ArticleVersion = version_class(self.Article)
        self.BlogPostVersion = version_class(self.BlogPost)


class TestJoinTableInheritanceWithRelationship(JoinTableInheritanceWithRelationshipTestCase):
    versioning_strategy = 'validity'

    def test_each_object_has_distinct_version_class(self):
        article_author = self.User(name=u'Article author')
        article = self.Article(author=article_author)
        blogpost_author = self.User(name=u'Blog author')
        blogpost = self.BlogPost(author=blogpost_author)
        textitem_author = self.User(name=u'Textitem author')
        textitem = self.TextItem(author=textitem_author)

        self.session.add(article)
        self.session.add(blogpost)
        self.session.add(textitem)
        self.session.commit()

        assert textitem.versions[0].author.name == u'Textitem author'
        assert article.versions[0].author.name == u'Article author'
        assert blogpost.versions[0].author.name == u'Blog author'
