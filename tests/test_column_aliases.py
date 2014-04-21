from pytest import mark
import sqlalchemy as sa
from sqlalchemy_continuum import version_class

from tests import TestCase, create_test_cases


class ColumnAliasesBaseTestCase(TestCase):
    def create_models(self):
        class TextItem(self.Model):
            __tablename__ = 'text_item'
            __versioned__ = {}

            id = sa.Column(
                '_id', sa.Integer, autoincrement=True, primary_key=True
            )

            name = sa.Column('_name', sa.Unicode(255))

        self.TextItem = TextItem


@mark.skipif('True')
class TestVersionTableWithColumnAliases(ColumnAliasesBaseTestCase):
    def test_column_reflection(self):
        assert '_id' in version_class(self.TextItem).__table__.c


class ColumnAliasesTestCase(ColumnAliasesBaseTestCase):
    def test_insert(self):
        item = self.TextItem(name=u'Something')
        self.session.add(item)
        self.session.commit()
        assert item.versions[0].name == u'Something'

    def test_revert(self):
        item = self.TextItem(name=u'Something')
        self.session.add(item)
        self.session.commit()
        item.name = u'Some other thing'
        self.session.commit()
        item.versions[0].revert()
        self.session.commit()

    def test_previous_for_deleted_parent(self):
        item = self.TextItem()
        item.name = u'Some item'
        item.content = u'Some content'
        self.session.add(item)
        self.session.commit()
        self.session.delete(item)
        self.session.commit()
        TextItemVersion = version_class(self.TextItem)

        versions = (
            self.session.query(TextItemVersion)
            .order_by(
                getattr(
                    TextItemVersion,
                    self.options['transaction_column_name']
                )
            )
        ).all()
        assert versions[1].previous.name == u'Some item'


create_test_cases(ColumnAliasesTestCase)
