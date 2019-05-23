import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


class ColumnExclusionTestCase(TestCase):
    def test_excluded_columns_not_included_in_version_class(self):
        cls = version_class(self.TextItem)
        manager = cls._sa_class_manager
        assert 'content' not in manager.keys()

    def test_versioning_with_column_exclusion(self):
        item = self.TextItem(name=u'Some textitem', content=u'Some content')
        self.session.add(item)
        self.session.commit()

        assert item.versions[0].name == u'Some textitem'

    def test_does_not_create_record_if_only_excluded_column_updated(self):
        item = self.TextItem(name=u'Some textitem')
        self.session.add(item)
        self.session.commit()
        item.content = u'Some content'
        self.session.commit()
        assert item.versions.count() == 1


class TestColumnExclusion(ColumnExclusionTestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'exclude': ['content']
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            content = sa.Column(sa.UnicodeText)

        self.TextItem = TextItem


class TestColumnExclusionWithAliasedColumn(ColumnExclusionTestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'exclude': ['content']
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            content = sa.Column('_content', sa.UnicodeText)

        self.TextItem = TextItem


class TestColumnExclusionWithRelationship(TestCase):
    def create_models(self):

        class Word(self.Model):
            __tablename__ = 'word'
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            word = sa.Column(sa.Unicode(255))

        class TextItemWord(self.Model):
            __tablename__ = 'text_item_word'
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            text_item_id = sa.Column(sa.Integer, sa.ForeignKey('text_item.id'), nullable=False)
            word_id = sa.Column(sa.Integer, sa.ForeignKey('word.id'), nullable=False)

        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {
                'exclude': ['content']
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))
            content = sa.orm.relationship(Word, secondary='text_item_word')

        self.TextItem = TextItem
        self.Word = Word

    def test_excluded_columns_not_included_in_version_class(self):
        cls = version_class(self.TextItem)
        manager = cls._sa_class_manager
        assert 'content' not in manager.keys()

    def test_versioning_with_column_exclusion(self):
        item = self.TextItem(name=u'Some textitem',
                             content=[self.Word(word=u'bird')])
        self.session.add(item)
        self.session.commit()

        assert item.versions[0].name == u'Some textitem'

    def test_does_not_create_record_if_only_excluded_column_updated(self):
        item = self.TextItem(name=u'Some textitem')
        self.session.add(item)
        self.session.commit()
        item.content.append(self.Word(word=u'Some content'))
        self.session.commit()
        assert item.versions.count() == 1
