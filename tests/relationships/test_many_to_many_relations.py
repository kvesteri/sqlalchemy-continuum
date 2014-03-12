import sqlalchemy as sa
from tests import TestCase, create_test_cases


class ManyToManyRelationshipsTestCase(TestCase):
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

    def test_version_relations(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        assert not article.versions[0].tags

    def test_single_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        assert len(article.versions[0].tags) == 1

    def test_multi_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        article.tags.append(self.Tag(name=u'another tag'))
        self.session.add(article)
        self.session.commit()
        assert len(article.versions[0].tags) == 2

    def test_delete_single_association(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        article.tags.remove(tag)
        article.name = u'Updated name'
        self.session.commit()

        assert len(article.versions[0].tags) == 1
        assert len(article.versions[1].tags) == 0

    def test_multi_delete_association(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        tag2 = self.Tag(name=u'another tag')
        article.tags.append(tag)
        article.tags.append(tag2)
        self.session.add(article)
        self.session.commit()
        article.tags.remove(tag)
        article.tags.remove(tag2)
        article.name = u'Updated name'
        self.session.commit()
        assert len(article.versions[1].tags) == 0


create_test_cases(ManyToManyRelationshipsTestCase)
