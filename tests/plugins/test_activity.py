import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager
from sqlalchemy_continuum.plugins import ActivityPlugin
from tests import TestCase


class TestActivity(TestCase):
    plugins = [ActivityPlugin()]

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
        )
        self.session.add(activity)
        self.session.commit()
        activity = self.session.query(versioning_manager.activity_cls).first()
        assert activity
        assert activity.transaction_id
        assert activity.object == article
        assert activity.object_version == article.versions[-1]
