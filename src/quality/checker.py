import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DatasetQualityResult:
    """Holds validation and quality metrics for a single dataset domain."""

    dataset_name: str
    source_count: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    missing_fields_count: int = 0
    duplicate_count: int = 0
    validation_error_count: int = 0
    valid_records: List[Dict[str, Any]] = field(default_factory=list)
    rejected_records: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DataQualityReport:
    """Aggregates quality metrics across the entire data engineering pipeline."""

    timestamp: str
    source_records: int = 0
    processed_records: int = 0
    rejected_records: int = 0
    missing_fields: int = 0
    duplicates: int = 0
    validation_errors: int = 0
    status: str = "PASS"  # PASS | WARN | FAIL
    dataset_details: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def audit_dataset(
    records: List[Dict[str, Any]],
    dataset_name: str,
    primary_key: str,
    required_fields: List[str],
    custom_validators: Optional[List[Tuple[str, Callable[[Dict[str, Any]], bool]]]] = None,
) -> DatasetQualityResult:
    """Performs comprehensive data quality checks on a raw record collection.

    Evaluates:
    1. Completeness: Ensures all required fields are present and not None/empty.
    2. Uniqueness: Flags duplicate primary key instances.
    3. Validity & Business Invariants: Applies custom predicate validators.

    Args:
        records: Incoming raw records from the bronze layer.
        dataset_name: Name of the domain (e.g., 'clubs', 'players').
        primary_key: Name of the unique identifier attribute.
        required_fields: List of mandatory attribute keys.
        custom_validators: Optional list of (error_description, check_function) tuples.

    Returns:
        DatasetQualityResult containing metrics, clean records, and quarantined errors.
    """
    result = DatasetQualityResult(dataset_name=dataset_name, source_count=len(records))
    seen_keys: Set[Any] = set()

    for idx, record in enumerate(records):
        record_issues: List[str] = []

        # 1. Completeness Check
        for field_name in required_fields:
            val = record.get(field_name)
            if val is None or (isinstance(val, str) and not val.strip()):
                record_issues.append(f"Missing required field: '{field_name}'")
                result.missing_fields_count += 1

        # 2. Uniqueness Check
        pk_val = record.get(primary_key)
        if pk_val is not None:
            if pk_val in seen_keys:
                record_issues.append(f"Duplicate primary key '{primary_key}'={pk_val}")
                result.duplicate_count += 1
            else:
                seen_keys.add(pk_val)

        # 3. Validity & Business Rule Checks
        if custom_validators:
            for description, validator_fn in custom_validators:
                try:
                    if not validator_fn(record):
                        record_issues.append(f"Validation failure: {description}")
                        result.validation_error_count += 1
                except Exception as err:
                    record_issues.append(f"Validator exception: {description} ({err})")
                    result.validation_error_count += 1

        # Triage Record: Accept or Reject
        if record_issues:
            result.rejected_count += 1
            quarantined = dict(record)
            quarantined["_rejection_reasons"] = record_issues
            quarantined["_record_index"] = idx
            result.rejected_records.append(quarantined)
            result.issues.extend(
                [{"record_index": idx, "pk": pk_val, "error": issue} for issue in record_issues]
            )
        else:
            result.valid_count += 1
            result.valid_records.append(record)

    logger.info(
        "Audited %s: %d source, %d valid, %d rejected.",
        dataset_name,
        result.source_count,
        result.valid_count,
        result.rejected_count,
    )
    return result


def build_quality_report(results: List[DatasetQualityResult]) -> DataQualityReport:
    """Aggregates individual dataset audit results into a cohesive DataQualityReport.

    Args:
        results: List of DatasetQualityResult objects for all audited tables.

    Returns:
        Consolidated DataQualityReport with pass/fail evaluation.
    """
    total_source = sum(r.source_count for r in results)
    total_valid = sum(r.valid_count for r in results)
    total_rejected = sum(r.rejected_count for r in results)
    total_missing = sum(r.missing_fields_count for r in results)
    total_duplicates = sum(r.duplicate_count for r in results)
    total_validation_errors = sum(r.validation_error_count for r in results)

    # Determine overall status
    if total_rejected == 0:
        status = "PASS"
    elif total_rejected < (total_source * 0.1):  # Less than 10% bad
        status = "WARN"
    else:
        status = "FAIL"

    details = {}
    for r in results:
        details[r.dataset_name] = {
            "source_records": r.source_count,
            "processed_records": r.valid_count,
            "rejected_records": r.rejected_count,
            "missing_fields": r.missing_fields_count,
            "duplicates": r.duplicate_count,
            "validation_errors": r.validation_error_count,
            "issues": r.issues,
        }

    return DataQualityReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_records=total_source,
        processed_records=total_valid,
        rejected_records=total_rejected,
        missing_fields=total_missing,
        duplicates=total_duplicates,
        validation_errors=total_validation_errors,
        status=status,
        dataset_details=details,
    )


def render_report_banner(report: DataQualityReport) -> str:
    """Renders a clean human-readable terminal banner matching executive specifications.

    Args:
        report: The consolidated DataQualityReport.

    Returns:
        Formatted multi-line text banner.
    """
    status_icon = "PASS" if report.status == "PASS" else ("WARN" if report.status == "WARN" else "FAIL")

    lines = [
        "EPL DATA QUALITY REPORT",
        "------------------------",
        f"Source records:       {report.source_records}",
        f"Processed records:    {report.processed_records}",
        f"Rejected records:     {report.rejected_records}",
        f"Missing fields:       {report.missing_fields}",
        f"Duplicates:           {report.duplicates}",
        f"Validation errors:    {report.validation_errors}",
        f"Status:                {status_icon}",
    ]
    return "\n".join(lines)


# =========================================================================
# DOMAIN VALIDATION RULE SPECIFICATIONS
# =========================================================================

def get_club_validators() -> List[Tuple[str, Callable[[Dict[str, Any]], bool]]]:
    """Domain validation predicates for EPL Clubs."""
    return [
        ("Stadium capacity must be greater than 0", lambda r: int(r.get("capacity", 0)) > 0),
        ("Founded year must be 1800 or later", lambda r: int(r.get("founded_year", 0)) >= 1800),
    ]


def get_player_validators() -> List[Tuple[str, Callable[[Dict[str, Any]], bool]]]:
    """Domain validation predicates for EPL Players."""
    return [
        ("Goals cannot be negative", lambda r: int(r.get("goals", 0)) >= 0),
        ("Assists cannot be negative", lambda r: int(r.get("assists", 0)) >= 0),
        ("Appearances cannot be negative", lambda r: int(r.get("appearances", 0)) >= 0),
        ("Jersey number must be between 1 and 99", lambda r: 1 <= int(r.get("jersey_number", 0)) <= 99),
    ]


def get_match_validators() -> List[Tuple[str, Callable[[Dict[str, Any]], bool]]]:
    """Domain validation predicates for EPL Matches."""
    score_regex = re.compile(r"^\d+\s*[-:]\s*\d+$")
    return [
        ("Home and away clubs must be distinct", lambda r: r.get("home_club_id") != r.get("away_club_id")),
        ("Score format must match 'X - Y'", lambda r: bool(score_regex.match(str(r.get("raw_score", "")).strip()))),
        ("Gameweek must be between 1 and 38", lambda r: 1 <= int(r.get("gameweek", 0)) <= 38),
    ]


def get_standings_validators() -> List[Tuple[str, Callable[[Dict[str, Any]], bool]]]:
    """Domain validation predicates for EPL Standings snapshots."""
    return [
        (
            "Games played invariant: played == won + drawn + lost",
            lambda r: int(r.get("played", 0))
            == (int(r.get("won", 0)) + int(r.get("drawn", 0)) + int(r.get("lost", 0))),
        ),
        (
            "Points invariant: points == (won * 3) + drawn",
            lambda r: int(r.get("points", 0))
            == ((int(r.get("won", 0)) * 3) + int(r.get("drawn", 0))),
        ),
    ]
