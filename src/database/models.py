import logging
from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import relationship

from src.database.connection import Base

logger = logging.getLogger(__name__)


class Club(Base):
    """Relational model for Premier League clubs.

    Demonstrates primary key definition, unique constraints, and 1-to-many relationships.
    """

    __tablename__ = "clubs"

    club_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    short_name = Column(String(10), nullable=False)
    stadium = Column(String(100), nullable=False)
    capacity = Column(Integer, nullable=False)
    city = Column(String(100), nullable=False)
    founded_year = Column(Integer, nullable=False)
    primary_color = Column(String(20), nullable=False, default="#1E293B")
    transformed_at = Column(String(50), nullable=False)

    __table_args__ = (
        CheckConstraint("capacity > 0", name="chk_club_capacity_positive"),
        CheckConstraint("founded_year >= 1800", name="chk_club_founded_year_valid"),
    )

    # Relationships
    players = relationship("Player", back_populates="club", cascade="all, delete-orphan")
    home_matches = relationship("Match", foreign_keys="Match.home_club_id", back_populates="home_club", cascade="all, delete-orphan")
    away_matches = relationship("Match", foreign_keys="Match.away_club_id", back_populates="away_club", cascade="all, delete-orphan")
    standing = relationship("Standing", back_populates="club", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "club_id": self.club_id,
            "name": self.name,
            "short_name": self.short_name,
            "stadium": self.stadium,
            "capacity": self.capacity,
            "city": self.city,
            "founded_year": self.founded_year,
            "primary_color": self.primary_color,
        }


class Player(Base):
    """Relational model for squad players.

    Demonstrates foreign key references, composite indexing, and cascading deletes.
    """

    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True, index=True)
    club_id = Column(Integer, ForeignKey("clubs.club_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    position = Column(String(50), nullable=False, index=True)
    nationality = Column(String(50), nullable=False)
    jersey_number = Column(Integer, nullable=False)
    appearances = Column(Integer, default=0, nullable=False)
    goals = Column(Integer, default=0, nullable=False, index=True)
    assists = Column(Integer, default=0, nullable=False)
    goal_contributions = Column(Integer, default=0, nullable=False)
    goals_per_game = Column(Float, default=0.0, nullable=False)
    transformed_at = Column(String(50), nullable=False)

    __table_args__ = (
        CheckConstraint("appearances >= 0", name="chk_player_appearances_nonneg"),
        CheckConstraint("goals >= 0", name="chk_player_goals_nonneg"),
        CheckConstraint("assists >= 0", name="chk_player_assists_nonneg"),
        Index("idx_player_club_position", "club_id", "position"),
    )

    # Relationships
    club = relationship("Club", back_populates="players")

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "club_id": self.club_id,
            "club_name": self.club.name if self.club else None,
            "name": self.name,
            "position": self.position,
            "nationality": self.nationality,
            "jersey_number": self.jersey_number,
            "appearances": self.appearances,
            "goals": self.goals,
            "assists": self.assists,
            "goal_contributions": self.goal_contributions,
            "goals_per_game": self.goals_per_game,
        }


class Match(Base):
    """Relational model for EPL match fixtures and results.

    Demonstrates dual foreign keys to the same table (home and away clubs)
    and table-level check constraints.
    """

    __tablename__ = "matches"

    match_id = Column(Integer, primary_key=True, index=True)
    gameweek = Column(Integer, nullable=False, index=True)
    home_club_id = Column(Integer, ForeignKey("clubs.club_id", ondelete="CASCADE"), nullable=False, index=True)
    away_club_id = Column(Integer, ForeignKey("clubs.club_id", ondelete="CASCADE"), nullable=False, index=True)
    match_date = Column(String(50), nullable=False, index=True)
    home_score = Column(Integer, nullable=False)
    away_score = Column(Integer, nullable=False)
    total_goals = Column(Integer, nullable=False)
    result = Column(String(20), nullable=False)
    status = Column(String(20), default="FINISHED", nullable=False)
    transformed_at = Column(String(50), nullable=False)

    __table_args__ = (
        CheckConstraint("home_club_id != away_club_id", name="chk_different_clubs"),
        CheckConstraint("home_score >= 0", name="chk_home_score_nonneg"),
        CheckConstraint("away_score >= 0", name="chk_away_score_nonneg"),
    )

    # Relationships
    home_club = relationship("Club", foreign_keys=[home_club_id], back_populates="home_matches")
    away_club = relationship("Club", foreign_keys=[away_club_id], back_populates="away_matches")

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "gameweek": self.gameweek,
            "home_club_id": self.home_club_id,
            "home_club_name": self.home_club.name if self.home_club else None,
            "away_club_id": self.away_club_id,
            "away_club_name": self.away_club.name if self.away_club else None,
            "match_date": self.match_date,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "score": f"{self.home_score} - {self.away_score}",
            "total_goals": self.total_goals,
            "result": self.result,
            "status": self.status,
        }


class Standing(Base):
    """Relational model for league standings snapshot.

    Demonstrates 1-to-1 relationship with unique foreign key constraint and analytical metrics.
    """

    __tablename__ = "standings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    club_id = Column(Integer, ForeignKey("clubs.club_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    position = Column(Integer, nullable=False, index=True)
    played = Column(Integer, nullable=False)
    won = Column(Integer, nullable=False)
    drawn = Column(Integer, nullable=False)
    lost = Column(Integer, nullable=False)
    goals_for = Column(Integer, nullable=False)
    goals_against = Column(Integer, nullable=False)
    goal_difference = Column(Integer, nullable=False)
    points = Column(Integer, nullable=False, index=True)
    points_per_game = Column(Float, nullable=False)
    win_percentage = Column(Float, nullable=False)
    form = Column(String(20), nullable=True)
    transformed_at = Column(String(50), nullable=False)

    __table_args__ = (
        CheckConstraint("played >= 0", name="chk_played_nonneg"),
        CheckConstraint("points >= 0", name="chk_points_nonneg"),
        Index("idx_standings_points_rank", "points", "goal_difference"),
    )

    # Relationship
    club = relationship("Club", back_populates="standing")

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "club_id": self.club_id,
            "club_name": self.club.name if self.club else None,
            "short_name": self.club.short_name if self.club else None,
            "played": self.played,
            "won": self.won,
            "drawn": self.drawn,
            "lost": self.lost,
            "goals_for": self.goals_for,
            "goals_against": self.goals_against,
            "goal_difference": self.goal_difference,
            "points": self.points,
            "points_per_game": self.points_per_game,
            "win_percentage": self.win_percentage,
            "form": self.form,
        }


def create_all_tables(engine: Engine) -> None:
    """Executes DDL to create all relational warehouse tables and indexes."""
    logger.info("Executing DDL table creation...")
    Base.metadata.create_all(engine)
    logger.info("All tables created successfully.")


def drop_all_tables(engine: Engine) -> None:
    """Drops all relational warehouse tables."""
    logger.info("Dropping all database tables...")
    Base.metadata.drop_all(engine)
    logger.info("All tables dropped.")
