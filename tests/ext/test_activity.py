import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager, current_transaction_id
from tests import TestCase


class TestActivity(TestCase):
    def create_models(self):
        TestCase.create_models(self)

        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = {
                'base_classes': (self.Model, )
            }

            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255), nullable=False)
        self.User = User

    def test_creates_activity_class(self):
        assert versioning_manager.activity_cls.__name__ == 'Activity'

    def test_create_activity_object(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.flush()
        activity = versioning_manager.activity_cls(
            object=article,
            verb=u'create',
            transaction_id=current_transaction_id
        )
        self.session.add(activity)
        self.session.commit()
