from tests import TestCase, create_test_cases


class OneToManyRelationshipsTestCase(TestCase):
    def test_single_insert(self):
        article = self.Article()
        article.name = u'Some article'
        article.content = u'Some content'
        article.tags.append(self.Tag(name=u'some tag'))
        self.session.add(article)
        self.session.commit()
        assert article.versions[0].tags.count()

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
        assert article.versions[0].tags.count() == 1
        assert article.versions[1].tags.count() == 1
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
        assert article.versions[0].tags.count() == 1
        assert article.versions[1].tags.count() == 2

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
        assert article.versions[0].tags.count() == 1
        assert article.versions[1].tags.count() == 0


create_test_cases(OneToManyRelationshipsTestCase)
