import sqlalchemy as sa
from sqlalchemy_continuum import version_class
from tests import TestCase


class TestCompositePrimaryKey(TestCase):
    def create_models(self):
        class User(self.Model):
            __tablename__ = 'user'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        class Team(self.Model):
            __tablename__ = 'team'
            __versioned__ = {}
            id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
            name = sa.Column(sa.Unicode(255))

        class TeamMember(self.Model):
            __tablename__ = 'team_member'
            __versioned__ = {}
            user_id = sa.Column(
                sa.Integer,
                sa.ForeignKey(User.id, ondelete='CASCADE'),
                primary_key=True,
                nullable=False
            )
            team_id = sa.Column(
                sa.Integer,
                sa.ForeignKey(Team.id, ondelete='CASCADE'),
                primary_key=True,
                nullable=False
            )
            role = sa.Column(sa.Unicode(255))

        self.Team = Team
        self.User = User
        self.TeamMember = TeamMember

    def test_composite_primary_key_on_version_tables(self):
        TeamMemberVersion = version_class(self.TeamMember)
        assert len(TeamMemberVersion.__table__.primary_key.columns) == 3

    def test_does_not_make_composite_primary_keys_not_nullable(self):
        TeamMemberVersion = version_class(self.TeamMember)

        assert not TeamMemberVersion.__table__.c.user_id.nullable


class TestCompositePrimaryKeyWithPkConstraint(TestCase):
    def create_models(self):
        class TeamMember(self.Model):
            __tablename__ = 'team_member'
            __versioned__ = {}
            user_id = sa.Column(
                sa.Integer,
                nullable=False
            )
            team_id = sa.Column(
                sa.Integer,
                nullable=False
            )
            role = sa.Column(sa.Unicode(255))
            __table_args__ = (
                sa.schema.PrimaryKeyConstraint('user_id', 'team_id'),
            )

        self.TeamMember = TeamMember

    def test_does_not_make_composite_primary_keys_not_nullable(self):
        TeamMemberVersion = version_class(self.TeamMember)

        assert not TeamMemberVersion.__table__.c.user_id.nullable
