import pytest
import sqlalchemy as sa
from sqlalchemy_continuum import versioning_manager
from sqlalchemy_continuum.plugins import ActivityPlugin
from tests import TestCase, QueryPool, uses_native_versioning


class ActivityTestCase(TestCase):
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

    def create_article(self):
        article = self.Article(name=u'Some article')
        self.session.add(article)
        return article

    def create_activity(self, object=None, target=None):
        activity = versioning_manager.activity_cls(
            object=object,
            target=target,
            verb=u'create',
        )
        self.session.add(activity)
        return activity


class TestActivity(ActivityTestCase):
    def test_creates_activity_class(self):
        assert versioning_manager.activity_cls.__name__ == 'Activity'

    def test_create_activity(self):
        article = self.create_article()
        self.session.flush()
        self.create_activity(article)
        self.session.commit()
        activity = self.session.query(versioning_manager.activity_cls).first()
        assert activity
        assert activity.transaction_id
        assert activity.object == article
        assert activity.object_version == article.versions[-1]

    def test_delete_activity(self):
        article = self.create_article()
        self.create_activity(article)
        self.session.commit()
        self.session.delete(article)
        activity = versioning_manager.activity_cls(
            object=article,
            verb=u'delete',
        )
        self.session.add(activity)
        self.session.commit()
        versions = (
            self.session.query(self.ArticleVersion)
            .order_by(sa.desc(self.ArticleVersion.transaction_id))
            .all()
        )
        assert activity
        assert activity.transaction_id
        assert activity.object is None
        assert activity.object_version == versions[-1]

    def test_activity_queries(self):
        article = self.create_article()
        self.session.flush()
        self.create_activity(article)
        self.session.commit()
        tag = self.Tag(name=u'some tag', article=article)
        self.session.add(tag)
        self.session.flush()
        Activity = versioning_manager.activity_cls
        activity = Activity(
            object=tag,
            target=article,
            verb=u'create',
        )
        self.session.add(activity)
        self.session.commit()
        activities = self.session.query(
            Activity
        ).filter(
            sa.or_(
                Activity.object == article,
                Activity.target == article
            )
        )
        assert activities.count() == 2


class TestObjectTxIdGeneration(ActivityTestCase):
    @pytest.mark.skipif('uses_native_versioning()')
    def test_does_not_query_db_if_version_obj_in_session(self):
        article = self.create_article()
        self.session.flush()
        self.create_activity(object=article)
        query_count = len(QueryPool.queries)
        self.session.commit()
        assert query_count + 1 == len(QueryPool.queries)

    def test_create_activity_with_multiple_existing_objects(self):
        article = self.create_article()
        self.session.commit()
        self.create_article()
        self.session.commit()
        activity = self.create_activity(article)
        self.session.commit()
        assert activity
        assert activity.transaction_id
        assert activity.object == article
        assert activity.object_version == article.versions[-1]


class TestTargetTxIdGeneration(ActivityTestCase):
    @pytest.mark.skipif('uses_native_versioning()')
    def test_does_not_query_db_if_version_obj_in_session(self):
        article = self.create_article()
        self.session.flush()
        self.create_activity(target=article)
        query_count = len(QueryPool.queries)
        self.session.commit()
        assert query_count + 1 == len(QueryPool.queries)

    def test_with_multiple_existing_targets(self):
        article = self.create_article()
        self.session.commit()
        self.create_article()
        self.session.commit()
        activity = self.create_activity(target=article)
        self.session.commit()
        assert activity
        assert activity.transaction_id
        assert activity.target == article
        assert activity.target_version == article.versions[-1]

    def test_activity_target(self):
        article = self.create_article()
        self.create_activity(article)
        self.session.commit()
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
