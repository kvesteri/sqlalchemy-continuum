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
