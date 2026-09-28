import pytest
from src.transform.calculate_standings import calculate_standings_and_form
from src.transform.clean_clubs import clean_clubs_data
from src.transform.clean_matches import clean_matches_data, parse_score_string
from src.transform.clean_players import clean_players_data


def test_clean_clubs_stripping_and_schema():
    raw = [
        {
            "club_id": 99,
            "name": "  Test FC  ",
            "short_name": "tst",
            "stadium": " Test Arena ",
            "capacity": 50000,
            "city": " London ",
            "founded_year": 1900,
            "primary_color": "#ffffff",
        }
    ]
    df = clean_clubs_data(raw)
    assert df.iloc[0]["name"] == "Test FC"
    assert df.iloc[0]["short_name"] == "TST"
    assert df.iloc[0]["stadium"] == "Test Arena"
    assert df.iloc[0]["city"] == "London"
    assert "transformed_at" in df.columns


def test_clean_players_position_normalization():
    raw = [
        {
            "player_id": 1,
            "club_id": 99,
            "name": " John Doe ",
            "position": "MIDFIELDER",
            "nationality": "England",
            "jersey_number": 10,
            "appearances": 10,
            "goals": 5,
            "assists": 5,
        }
    ]
    df = clean_players_data(raw)
    assert df.iloc[0]["name"] == "John Doe"
    assert df.iloc[0]["position"] == "Midfielder"
    assert df.iloc[0]["goal_contributions"] == 10
    assert df.iloc[0]["goals_per_game"] == 0.5


def test_parse_score_string():
    h, a = parse_score_string("3 - 1")
    assert h == 3
    assert a == 1

    h2, a2 = parse_score_string("0:0")
    assert h2 == 0
    assert a2 == 0


def test_clean_matches_derivation():
    raw = [
        {
            "match_id": 1,
            "gameweek": 1,
            "home_club_id": 10,
            "away_club_id": 20,
            "match_date": "2024-08-17 15:00:00",
            "raw_score": "2 - 1",
            "status": "FINISHED",
        }
    ]
    df = clean_matches_data(raw)
    assert df.iloc[0]["home_score"] == 2
    assert df.iloc[0]["away_score"] == 1
    assert df.iloc[0]["total_goals"] == 3
    assert df.iloc[0]["result"] == "HOME_WIN"


def test_standings_invariant_validation():
    # Valid record
    valid_raw = [
        {"club_id": 1, "played": 2, "won": 1, "drawn": 1, "lost": 0, "goals_for": 3, "goals_against": 1, "points": 4}
    ]
    df = calculate_standings_and_form(valid_raw)
    assert df.iloc[0]["points"] == 4
    assert df.iloc[0]["goal_difference"] == 2

    # Inconsistent games played should raise ValueError
    invalid_played = [
        {"club_id": 1, "played": 5, "won": 1, "drawn": 1, "lost": 0, "goals_for": 3, "goals_against": 1, "points": 4}
    ]
    with pytest.raises(ValueError):
        calculate_standings_and_form(invalid_played)
