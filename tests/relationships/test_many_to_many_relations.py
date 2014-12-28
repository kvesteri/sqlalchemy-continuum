import pytest
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
        if (
            self.driver == 'mysql' and
            self.connection.dialect.server_version_info < (5, 6)
        ):
            pytest.skip()

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


class TestManyToManySelfReferential(TestCase):
    
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        article_references = sa.Table(
            'article_references',
            self.Model.metadata,
            sa.Column(
                'referring_id',
                sa.Integer,
                sa.ForeignKey('article.id'),
                primary_key=True,
            ),
            sa.Column(
                'referred_id',
                sa.Integer,
                sa.ForeignKey('article.id'),
                primary_key=True
            )
        )

        Article.references = sa.orm.relationship(
            Article,
            secondary=article_references,
            primaryjoin=Article.id == article_references.c.referring_id,
            secondaryjoin=Article.id == article_references.c.referred_id,
            backref='cited_by'
        )

        self.Article = Article
        self.referenced_articles_table = article_references


    def test_single_insert(self):

        article = self.Article(name=u'article')
        reference1 = self.Article(name=u'referred article 1')
        article.references.append(reference1)
        self.session.add(article)
        self.session.commit()

        assert len(article.versions[0].references) == 1
        assert reference1.versions[0] in article.versions[0].references

        assert len(reference1.versions[0].cited_by) == 1
        assert article.versions[0] in reference1.versions[0].cited_by
        
        
    def test_multiple_inserts_over_multiple_transactions(self):
        if (
            self.driver == 'mysql' and
            self.connection.dialect.server_version_info < (5, 6)
        ):
            pytest.skip()

        # create 1 article with 1 reference
        article = self.Article(name=u'article')
        reference1 = self.Article(name=u'reference 1')
        article.references.append(reference1)
        self.session.add(article)
        self.session.commit()

        # update existing, add a 2nd reference
        article.name = u'Updated article'
        reference1.name = u'Updated reference 1'
        reference2 = self.Article(name=u'reference 2')
        article.references.append(reference2)
        self.session.commit()

        # update only the article and reference 1
        article.name = u'Updated article x2'
        reference1.name = u'Updated reference 1 x2'
        self.session.commit()

        assert len(article.versions[1].references) == 2
        assert reference1.versions[1] in article.versions[1].references
        assert reference2.versions[0] in article.versions[1].references

        assert len(reference1.versions[1].cited_by) == 1
        assert article.versions[1] in reference1.versions[1].cited_by

        assert len(reference2.versions[0].cited_by) == 1
        assert article.versions[1] in reference2.versions[0].cited_by

        assert len(article.versions[2].references) == 2
        assert reference1.versions[2] in article.versions[2].references
        assert reference2.versions[0] in article.versions[2].references

        assert len(reference1.versions[2].cited_by) == 1
        assert article.versions[2] in reference1.versions[2].cited_by