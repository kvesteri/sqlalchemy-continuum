import sqlalchemy as sa
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
                sa.Integer, sa.ForeignKey(User.id), primary_key=True
            )
            team_id = sa.Column(
                sa.Integer, sa.ForeignKey(Team.id), primary_key=True
            )
            role = sa.Column(sa.Unicode(255))

        self.Team = Team
        self.User = User
        self.TeamMember = TeamMember

    def test_composite_primary_key_on_history_tables(self):
        TeamMemberHistory = self.TeamMember.__versioned__['class']
        assert len(TeamMemberHistory.__table__.primary_key.columns) == 3
