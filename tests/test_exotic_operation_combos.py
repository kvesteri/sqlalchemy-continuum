from tests import TestCase, create_test_cases


class ExoticOperationCombosTestCase(TestCase):
    def test_insert_deleted_object(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.flush()
        self.session.commit()

        self.session.delete(article)
        article2 = self.Article(id=article.id, name=u'Some article 2')
        self.session.add(article2)
        self.session.commit()
        assert article2.versions.count() == 2
        assert article2.versions[0].operation_type == 0
        assert article2.versions[1].operation_type == 1

    def test_insert_deleted_and_flushed_object(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.commit()
        assert article.versions.count()

        self.session.delete(article)
        self.session.flush()
        assert article.versions.count() == 2
        article2 = self.Article(id=article.id, name=u'Some other article')
        self.session.add(article2)
        self.session.commit()
        assert article2.versions.count() == 2
        assert article2.versions[0].operation_type == 0
        assert article2.versions[1].operation_type == 1

    def test_replace_deleted_object_with_update(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article2 = self.Article()
        article2.name = u'Another article'
        article2.content = u'Some other content'
        self.session.add(article)
        self.session.add(article2)
        self.session.commit()

        self.session.delete(article)
        self.session.flush()

        article2.id = article.id
        self.session.commit()
        assert article2.versions.count() == 2
        assert article2.versions[0].operation_type == 0
        assert article2.versions[1].operation_type == 1

    def test_insert_flushed_object(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        self.session.add(article)
        self.session.flush()
        self.session.commit()

        assert article.versions.count() == 1
        assert article.versions[0].operation_type == 0


# Skip the tests until SQLAlchemy has renewed its UOW handling:
create_test_cases(ExoticOperationCombosTestCase)
