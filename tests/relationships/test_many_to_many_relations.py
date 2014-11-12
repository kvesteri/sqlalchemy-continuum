import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager

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
                sa.ForeignKey('article.id'),
                primary_key=True,
            ),
            sa.Column(
                'tag_id',
                sa.Integer,
                sa.ForeignKey('tag.id'),
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

    def test_collection_with_multiple_entries(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        article.tags = [
            self.Tag(name=u'some tag'),
            self.Tag(name=u'another tag')
        ]
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
        tags = article.versions[1].tags
        assert len(tags) == 0

    def test_delete_multiple_associations(self):
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

    def test_remove_node_but_not_the_link(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        self.session.delete(tag)
        article.name = u'Updated name'
        self.session.commit()
        tags = article.versions[1].tags
        assert len(tags) == 0

    def test_multiple_parent_objects_added_within_same_transaction(self):
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
        tags = article.versions[0].tags
        assert tags == [tag.versions[0]]

    def test_relations_with_varying_transactions(self):
        # one article with one tag
        article = self.Article(name=u'Some article')
        tag1 = self.Tag(name=u'some tag')
        article.tags.append(tag1)
        self.session.add(article)
        self.session.commit()

        # update article and tag, add a 2nd tag
        tag2 = self.Tag(name=u'some other tag')
        article.tags.append(tag2)
        tag1.name = u'updated tag1'
        article.name = u'updated article'
        self.session.commit()

        # update article and first tag only
        tag1.name = u'updated tag1 x2'
        article.name = u'updated article x2'
        self.session.commit()

        assert len(article.versions[0].tags) == 1
        assert article.versions[0].tags[0] is tag1.versions[0]

        assert len(article.versions[1].tags) == 2
        assert tag1.versions[1] in article.versions[1].tags
        assert tag2.versions[0] in article.versions[1].tags

        assert len(article.versions[2].tags) == 2
        assert tag1.versions[2] in article.versions[2].tags
        assert tag2.versions[0] in article.versions[2].tags


create_test_cases(ManyToManyRelationshipsTestCase)


class TestManyToManyRelationshipWithViewOnly(TestCase):
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
                sa.ForeignKey('article.id'),
                primary_key=True,
            ),
            sa.Column(
                'tag_id',
                sa.Integer,
                sa.ForeignKey('tag.id'),
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
            viewonly=True
        )

        self.article_tag = article_tag
        self.Article = Article
        self.Tag = Tag

    def test_does_not_add_association_table_to_manager_registry(self):
        assert self.article_tag not in versioning_manager.association_tables
