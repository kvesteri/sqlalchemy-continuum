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

    def create_article(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        self.session.flush()
        return article

    def create_activity(self, obj):
        activity = versioning_manager.activity_cls(
            object=obj,
            verb=u'create',
        )
        self.session.add(activity)
        self.session.commit()
        return activity

    def test_create_activity(self):
        article = self.create_article()
        self.create_activity(article)
        activity = self.session.query(versioning_manager.activity_cls).first()
        assert activity
        assert activity.transaction_id
        assert activity.object == article
        assert activity.object_version == article.versions[-1]

    def test_delete_activity(self):
        article = self.create_article()
        self.create_activity(article)
        self.session.delete(article)
        activity = versioning_manager.activity_cls(
            object=article,
            verb=u'delete',
        )
        self.session.add(activity)
        self.session.commit()
        versions = (
            self.session.query(self.ArticleHistory)
            .order_by(sa.desc(self.ArticleHistory.transaction_id))
            .all()
        )
        assert activity
        assert activity.transaction_id
        assert activity.object is None
        assert activity.object_version == versions[-1]

    def test_activity_target(self):
        article = self.create_article()
        self.create_activity(article)
        tag = self.Tag(name=u'some tag', article=article)
        self.session.add(tag)
        self.session.flush()
        activity = versioning_manager.activity_cls(
            object=tag,
            target=article,
            verb=u'create',
        )
        self.session.add(activity)
        self.session.commit()
        activity = self.session.query(
            versioning_manager.activity_cls
        ).filter_by(id=activity.id).one()
        assert activity
        assert activity.transaction_id
        assert activity.object == tag
        assert activity.object_version == tag.versions[-1]
        assert activity.target == article
        assert activity.target_version == article.versions[-1]
