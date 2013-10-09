from tests import TestCase


class VersionModelAccessorsTestCase(TestCase):
    def test_previous_for_first_version(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        assert not article.versions[0].previous

    def test_previous_for_live_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()
        version = article.versions[1]

        assert version.previous.name == u'Some article'

    def test_previous_for_deleted_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        self.session.delete(article)
        self.session.commit()
        versions = (
            self.session.query(self.ArticleHistory)
            .order_by(self.ArticleHistory.id)
        ).all()
        assert versions[1].previous.name == u'Some article'

    def test_previous_chaining(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated article'
        self.session.commit()
        self.session.delete(article)
        self.session.commit()
        version = (
            self.session.query(self.ArticleHistory)
            .order_by(self.ArticleHistory.id)
        ).all()[-1]
        assert version.previous.previous

    def test_next_for_last_version(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        assert not article.versions[0].next

    def test_next_for_live_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        article.name = u'Updated name'
        article.content = u'Updated content'
        self.session.commit()
        version = article.versions[0]

        assert version.next.name == u'Updated name'

    def test_next_for_deleted_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        version = article.versions[0]
        self.session.delete(article)
        self.session.commit()

        assert version.next

    def test_chaining_next(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        article.name = u'Updated article'
        self.session.commit()
        article.content = u'Updated content'
        self.session.commit()

        versions = article.versions.all()
        version = versions[0]
        assert version.next == versions[1]
        assert version.next.next == versions[2]

    def test_index_for_deleted_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        self.session.delete(article)
        self.session.commit()

        versions = (
            self.session.query(self.ArticleHistory)
            .order_by(self.ArticleHistory.id)
        ).all()
        assert versions[0].index == 0
        assert versions[1].index == 1

    def test_index_for_live_parent(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()

        assert article.versions[0].index == 0


class TestAccessorsWithSubqueryStrategy(VersionModelAccessorsTestCase):
    versioning_strategy = 'subquery'


class TestAccessorsWithValidityStrategy(VersionModelAccessorsTestCase):
    versioning_strategy = 'validity'
