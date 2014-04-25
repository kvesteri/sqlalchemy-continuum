from pytest import raises

from sqlalchemy_continuum import (
    ClassNotVersioned,
    transaction_class,
    versioning_manager
)
from tests import TestCase


class TestTransactionClass(TestCase):
    def test_with_versioned_class(self):
        assert (
            transaction_class(self.Article) ==
            versioning_manager.transaction_cls
        )

    def test_with_unknown_type(self):
        with raises(ClassNotVersioned):
            transaction_class(None)
