import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


class TestCommonBaseClass(TestCase):
    def create_models(self):
        class BaseModel(self.Model):
            __tablename__ = 'base_model'
            __versioned__ = {}

            id = sa.Column(sa.Integer, primary_key=True)
            discriminator = sa.Column(sa.String(50), index=True)

            __mapper_args__ = {
                'polymorphic_on': discriminator,
                'polymorphic_identity': 'product'
            }

        class FirstLevel(BaseModel):
            __tablename__ = 'first_level'

            id = sa.Column(sa.Integer, sa.ForeignKey('base_model.id'), primary_key=True)

            __mapper_args__ = {
                'polymorphic_identity': 'first_level'
            }

        class SecondLevel(FirstLevel):
            __mapper_args__ = {
                'polymorphic_identity': 'second_level'
            }

        self.BaseModel = BaseModel
        self.FirstLevel = FirstLevel
        self.SecondLevel = SecondLevel

    def test_sa_inheritance_with_no_distinct_table_has_right_translation_class(self):
        class_ = version_class(self.BaseModel)
        assert class_.__name__ == 'BaseModelVersion'
        assert class_.__table__.name == 'base_model_version'
        class_ = version_class(self.FirstLevel)
        assert class_.__name__ == 'FirstLevelVersion'
        assert class_.__table__.name == 'first_level_version'
        class_ = version_class(self.SecondLevel)
        assert class_.__name__ == 'SecondLevelVersion'
        assert class_.__table__.name == 'first_level_version'
