from tests import TestCase


class TestVersions(TestCase):
    def test_versions_ordered_by_transaction_id(self):
        names = [
            u'Some article',
            u'Update 1 article',
            u'Update 2 article',
            u'Update 3 article',
        ]

        article = self.Article(name=names[0])
        self.session.add(article)
        self.session.commit()
        article.name = names[1]
        self.session.commit()
        article.name = names[2]
        self.session.commit()
        article.name = names[3]
        self.session.commit()

        for index, name in enumerate(names):
            assert article.versions[index].name == name
