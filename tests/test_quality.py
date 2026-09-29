import pytest
from src.quality.checker import (
    audit_dataset,
    build_quality_report,
    get_club_validators,
    get_player_validators,
    get_standings_validators,
    render_report_banner,
)


def test_audit_dataset_all_valid():
    records = [
        {
            "club_id": 1,
            "name": "Arsenal",
            "short_name": "ARS",
            "stadium": "Emirates Stadium",
            "capacity": 60704,
            "founded_year": 1886,
        }
    ]
    result = audit_dataset(
        records=records,
        dataset_name="clubs",
        primary_key="club_id",
        required_fields=["club_id", "name", "short_name", "stadium", "capacity", "founded_year"],
        custom_validators=get_club_validators(),
    )
    assert result.source_count == 1
    assert result.valid_count == 1
    assert result.rejected_count == 0
    assert result.missing_fields_count == 0
    assert result.duplicate_count == 0
    assert result.validation_error_count == 0
    assert len(result.valid_records) == 1


def test_audit_dataset_missing_required_field():
    records = [
        {
            "club_id": 2,
            "name": "",  # Empty name
            "short_name": "AVL",
            "stadium": "Villa Park",
            "capacity": 42640,
            "founded_year": 1874,
        },
        {
            "club_id": 3,
            # Missing stadium entirely
            "name": "Chelsea",
            "short_name": "CHE",
            "capacity": 40343,
            "founded_year": 1905,
        },
    ]
    result = audit_dataset(
        records=records,
        dataset_name="clubs",
        primary_key="club_id",
        required_fields=["club_id", "name", "short_name", "stadium", "capacity", "founded_year"],
        custom_validators=get_club_validators(),
    )
    assert result.source_count == 2
    assert result.valid_count == 0
    assert result.rejected_count == 2
    assert result.missing_fields_count == 2
    assert len(result.rejected_records) == 2


def test_audit_dataset_duplicate_primary_key():
    records = [
        {"player_id": 101, "club_id": 1, "name": "Bukayo Saka", "position": "Forward", "jersey_number": 7, "goals": 14, "assists": 9, "appearances": 32},
        {"player_id": 101, "club_id": 1, "name": "Bukayo Saka Clone", "position": "Forward", "jersey_number": 7, "goals": 0, "assists": 0, "appearances": 0},
    ]
    result = audit_dataset(
        records=records,
        dataset_name="players",
        primary_key="player_id",
        required_fields=["player_id", "club_id", "name", "position", "jersey_number"],
        custom_validators=get_player_validators(),
    )
    assert result.source_count == 2
    assert result.valid_count == 1
    assert result.rejected_count == 1
    assert result.duplicate_count == 1


def test_audit_dataset_business_invariant_failure():
    # Inconsistent standings math: played (5) != won(4) + drawn(0) + lost(0) = 4
    records = [
        {"club_id": 5, "played": 5, "won": 4, "drawn": 0, "lost": 0, "goals_for": 10, "goals_against": 2, "points": 12}
    ]
    result = audit_dataset(
        records=records,
        dataset_name="standings",
        primary_key="club_id",
        required_fields=["club_id", "played", "won", "drawn", "lost", "goals_for", "goals_against", "points"],
        custom_validators=get_standings_validators(),
    )
    assert result.source_count == 1
    assert result.valid_count == 0
    assert result.rejected_count == 1
    assert result.validation_error_count == 1


def test_render_report_banner_and_status():
    records = [
        {
            "club_id": 1,
            "name": "Arsenal",
            "short_name": "ARS",
            "stadium": "Emirates Stadium",
            "capacity": 60704,
            "founded_year": 1886,
        }
    ]
    res = audit_dataset(records, "clubs", "club_id", ["club_id", "name", "stadium"], get_club_validators())
    report = build_quality_report([res])
    assert report.status == "PASS"
    assert report.source_records == 1
    assert report.processed_records == 1

    banner = render_report_banner(report)
    assert "EPL DATA QUALITY REPORT" in banner
    assert "Source records:       1" in banner
    assert "Status:                PASS" in banner
