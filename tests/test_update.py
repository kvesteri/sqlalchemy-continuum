from tests import TestCase


class TestUpdate(TestCase):
    def test_creates_versions_on_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'

        self.session.commit()
        self.session.refresh(article)
        version = article.versions.all()[-1]
        assert version.name == u'Updated name'
        assert version.content == u'Updated content'
        assert version.transaction.id == version.transaction_id

    def test_partial_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.content = u'Updated content'

        self.session.commit()
        self.session.refresh(article)
        version = article.versions.all()[-1]
        assert version.name == u'Some article'
        assert version.content == u'Updated content'
        assert version.transaction.id == version.transaction_id

    def test_partial_raw_sql_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        self.connection.execute(
            "UPDATE article SET content = 'Updated content'"
        )
        self.session.commit()
        version = article.versions.all()[-1]
        assert version.name == u'Some article'
        assert version.content == u'Updated content'
