import sqlalchemy as sa
from packaging import version
from pytest import mark

from tests import TestCase


@mark.skipif("version.parse(sa.__version__) >= version.parse('2.0')")
class TestCompatibility1_4(TestCase):
    def test_execute_string_select(self):
        self.connection.execute('select 1')

    def test_execute_string_insert(self):
        self.connection.execute(
            'insert into article (id, name) values (1, "Test article")'
        )
