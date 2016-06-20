import sqlalchemy as sa
from sqlalchemy_continuum import get_versioning_manager
from tests import TestCase


class ChangeSetBaseTestCase(TestCase):
    def test_changeset_for_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].changeset == {
            'content': [None, u'Some content'],
            'name': [None, u'Some article'],
            'id': [None, 1]
        }

    def test_changeset_for_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()

        assert article.versions[1].changeset == {
            'content': [u'Some content', u'Updated content'],
            'name': [u'Some article', u'Updated name']
        }


class ChangeSetTestCase(ChangeSetBaseTestCase):
    def test_changeset_for_history_that_does_not_have_first_insert(self):
        tx_log_class = get_versioning_manager(self.Article).transaction_cls
        tx_log = tx_log_class(issued_at=sa.func.now())
        if self.options['native_versioning']:
            tx_log.id = sa.func.txid_current()

        self.session.add(tx_log)
        self.session.commit()

        # Needed when using native versioning
        self.session.expunge_all()
        tx_log = self.session.query(tx_log_class).first()

        self.session.execute(
            '''INSERT INTO article_version
            (id, %s, name, content, operation_type)
            VALUES
            (1, %d, 'something', 'some content', 1)
            ''' % (self.transaction_column_name, tx_log.id)
        )

        assert self.session.query(self.ArticleVersion).first().changeset == {
            'content': [None, 'some content'],
            'id': [None, 1],
            'name': [None, 'something']
        }


class TestChangeSetWithValidityStrategy(ChangeSetTestCase):
    versioning_strategy = 'validity'


class TestChangeSetWithCustomTransactionColumn(ChangeSetTestCase):
    transaction_column_name = 'tx_id'


class TestChangeSetWhenParentContainsAdditionalColumns(ChangeSetTestCase):
    def create_models(self):
        class Article(self.Model):
            __tablename__ = 'article'
            __versioned__ = {
                'base_classes': (self.Model,)
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
            content = sa.Column(sa.UnicodeText)
            description = sa.Column(sa.UnicodeText)

        class Tag(self.Model):
            __tablename__ = 'tag'
            __versioned__ = {
                'base_classes': (self.Model,)
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
            article = sa.orm.relationship(Article, backref='tags')

        Article.tag_count = sa.orm.column_property(
            sa.select([sa.func.count(Tag.id)])
                .where(Tag.article_id == Article.id)
                .correlate_except(Tag)
        )

        self.Article = Article
        self.Tag = Tag
