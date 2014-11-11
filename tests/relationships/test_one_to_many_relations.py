import sqlalchemy as sa
from tests import TestCase, create_test_cases


class OneToManyRelationshipsTestCase(TestCase):
    def test_single_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tags

    def test_insert_in_a_separate_transaction(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        self.session.add(self.Tag(name=u'some tag', article=article))
        self.session.commit()
        assert article.versions.count() == 1

    def test_relationships_for_history_objects(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        version = article.versions.all()[0]
        assert version.name == u'Some article'
        assert version.content == u'Some content'
        version = article.tags[0].versions.all()[0]
        assert version.name == u'some tag'

    def test_consecutive_inserts_and_removes(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        article.tags.remove(tag)
        self.session.commit()
        assert article.versions.count() == 1
        article.tags.append(self.Tag(name=u'Some other tag'))
        article.name = u'Updated article'
        self.session.commit()

        assert article.versions.count() == 2
        assert len(article.versions[0].tags) == 1
        assert len(article.versions[1].tags) == 1
        assert article.versions[1].tags[0].name == u'Some other tag'

    def test_multiple_inserts_in_consecutive_transactions(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        article.tags.append(self.Tag(name=u'other tag'))
        article.name = u'Updated article'
        self.session.commit()
        assert len(article.versions[0].tags) == 1
        assert len(article.versions[1].tags) == 2

    def test_children_inserts_with_varying_versions(self):
        # one article with one tag
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()

        # update the article and the tag, and add a 2nd tag
        article.name = u'Updated article'
        tag.name = u'updated tag'
        tag2 = self.Tag(name=u'other tag',
                        article=article)
        self.session.commit()

        # update the article and the tag again
        article.name = u'Updated again article'
        tag.name = u'updated again tag'
        self.session.commit()

        assert len(article.versions[0].tags) == 1
        assert article.versions[0].tags[0] is tag.versions[0]

        assert len(article.versions[1].tags) == 2
        assert tag.versions[1] in article.versions[1].tags
        assert tag2.versions[0] in article.versions[1].tags

        assert len(article.versions[2].tags) == 2
        assert tag.versions[2] in article.versions[2].tags
        assert tag2.versions[0] in article.versions[2].tags

    def test_delete(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        tag = self.Tag(name=u'some tag')
        article.tags.append(tag)
        self.session.add(article)
        self.session.commit()
        self.session.delete(tag)
        article.name = u'Updated article'
        self.session.commit()
        assert len(article.versions[0].tags) == 1
        assert len(article.versions[1].tags) == 0


create_test_cases(OneToManyRelationshipsTestCase)


class TestOneToManyWithUseListFalse(TestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        class Category(self.Model):
            __tablename__ = 'category'
            __versioned__ = {}

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(
                Article,
                backref=sa.orm.backref(
                    'category',
                    uselist=False
                )
            )

        self.Article = Article
        self.Category = Category

    def test_single_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        category = self.Category(name=u'some category')
        article.category = category
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].category == category.versions[0]
