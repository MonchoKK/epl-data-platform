from src.ingestion.club_ingestion import fetch_raw_clubs
from src.ingestion.match_ingestion import fetch_raw_matches
from src.ingestion.player_ingestion import fetch_raw_players
from src.ingestion.standings_ingestion import fetch_raw_standings


def test_fetch_raw_clubs_structure():
    clubs = fetch_raw_clubs()
    assert isinstance(clubs, list)
    assert len(clubs) > 0
    first = clubs[0]
    assert "club_id" in first
    assert "name" in first
    assert "stadium" in first
    assert "_ingested_at" in first


def test_fetch_raw_players_structure():
    players = fetch_raw_players()
    assert isinstance(players, list)
    assert len(players) > 0
    first = players[0]
    assert "player_id" in first
    assert "club_id" in first
    assert "position" in first
    assert "_ingested_at" in first


def test_fetch_raw_matches_structure():
    matches = fetch_raw_matches()
    assert isinstance(matches, list)
    assert len(matches) > 0
    first = matches[0]
    assert "match_id" in first
    assert "home_club_id" in first
    assert "away_club_id" in first
    assert "raw_score" in first


def test_fetch_raw_standings_structure():
    standings = fetch_raw_standings()
    assert isinstance(standings, list)
    assert len(standings) > 0
    first = standings[0]
    assert "club_id" in first
    assert "played" in first
    assert "points" in first
