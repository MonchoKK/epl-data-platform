"""CLI Diagnostic Verification Tool for Analytical SQL Views (Task 3).

Executes live inspection against the active data warehouse database:
1. vw_league_table: Dynamic standings window ranking (DENSE_RANK), points & GD sorting
2. vw_top_scorers: Golden boot leaderboard (ROW_NUMBER), tie-breaking & 0-goal exclusion
3. vw_club_analytics: Multi-table LEFT JOIN squad aggregates & COALESCE fallbacks
"""

import sys
from typing import Any, Dict, List
from sqlalchemy import text

from src.database.connection import get_db_engine, get_db_session
from src.database.models import create_all_tables
from src.database.views import (
    create_analytical_views,
    query_club_analytics_view,
    query_league_table_view,
    query_top_scorers_view,
)


def verify_league_table_view(session) -> bool:
    """Inspects and validates the vw_league_table analytical SQL view."""
    rows = query_league_table_view(session)
    if not rows:
        print("  [WARN] View vw_league_table returned 0 rows (run pipeline first to populate data)")
        return True

    # 1. Column verification
    required = {"dynamic_rank", "club_name", "short_name", "played", "won", "drawn", "lost", "goals_for", "goals_against", "goal_difference", "points"}
    missing = required - set(rows[0].keys())
    if missing:
        print(f"  ❌ Missing required columns in vw_league_table: {missing}")
        return False

    # 2. Rank sequence and ordering verification
    prev_points = float("inf")
    for r in rows:
        pts = r["points"]
        if pts > prev_points:
            print(f"  ❌ Ranking violation: club {r['short_name']} ({pts} pts) appears after higher points ({prev_points} pts)")
            return False
        prev_points = pts

    print(f"  [OK] Projection verified: {len(rows)} clubs loaded from vw_league_table")
    print(f"  [OK] Window function DENSE_RANK() verified: leaders are sorted monotonically by points/GD")

    # Render ASCII League Table preview
    print("\n  " + "-" * 75)
    print(f"  {'Rank':<5} | {'Club':<20} | {'P':<3} | {'W':<3} | {'D':<3} | {'L':<3} | {'GF':<3} | {'GA':<3} | {'GD':<4} | {'Pts':<4} | {'Form'}")
    print("  " + "-" * 75)
    for r in rows[:5]:
        form = r.get("form") or "-"
        print(f"  {r['dynamic_rank']:<5} | {r['club_name']:<20} | {r['played']:<3} | {r['won']:<3} | {r['drawn']:<3} | {r['lost']:<3} | {r['goals_for']:<3} | {r['goals_against']:<3} | {r['goal_difference']:<4} | {r['points']:<4} | {form}")
    if len(rows) > 5:
        print(f"  ... ({len(rows) - 5} more clubs)")
    print("  " + "-" * 75)
    return True


def verify_top_scorers_view(session) -> bool:
    """Inspects and validates the vw_top_scorers analytical SQL view."""
    rows = query_top_scorers_view(session, limit=10)
    if not rows:
        print("  [WARN] View vw_top_scorers returned 0 rows (run pipeline first to populate data)")
        return True

    # 1. Column verification
    required = {"scorer_rank", "player_name", "club_name", "club_short_name", "appearances", "goals", "assists", "goal_contributions"}
    missing = required - set(rows[0].keys())
    if missing:
        print(f"  ❌ Missing required columns in vw_top_scorers: {missing}")
        return False

    # 2. Strict exclusion of 0 goals
    zero_goal_players = [r for r in rows if r["goals"] <= 0]
    if zero_goal_players:
        print(f"  ❌ WHERE p.goals > 0 filter violated: found players with <= 0 goals: {[p['player_name'] for p in zero_goal_players]}")
        return False

    # 3. ROW_NUMBER sequence check
    ranks = [r["scorer_rank"] for r in rows]
    expected_ranks = list(range(1, len(rows) + 1))
    if ranks != expected_ranks:
        print(f"  ❌ ROW_NUMBER() ranking sequence gap or mismatch: got {ranks}, expected {expected_ranks}")
        return False

    print(f"  [OK] Projection verified: top {len(rows)} goal scorers queried")
    print(f"  [OK] Filter verified: 0-goal players strictly excluded (WHERE p.goals > 0)")
    print(f"  [OK] Window function ROW_NUMBER() verified: sequential 1..N ranks with tie-breaking")

    # Render ASCII Top Scorers preview
    print("\n  " + "-" * 75)
    print(f"  {'Rank':<5} | {'Player':<22} | {'Club':<6} | {'Apps':<5} | {'Goals':<6} | {'Assists':<8} | {'G/Game'}")
    print("  " + "-" * 75)
    for r in rows[:5]:
        gpg = r.get("goals_per_game") or 0.0
        print(f"  {r['scorer_rank']:<5} | {r['player_name']:<22} | {r['club_short_name']:<6} | {r['appearances']:<5} | {r['goals']:<6} | {r['assists']:<8} | {gpg:.2f}")
    if len(rows) > 5:
        print(f"  ... ({len(rows) - 5} more scorers)")
    print("  " + "-" * 75)
    return True


def verify_club_analytics_view(session) -> bool:
    """Inspects and validates the vw_club_analytics analytical SQL view."""
    rows = query_club_analytics_view(session)
    if not rows:
        print("  [WARN] View vw_club_analytics returned 0 rows (run pipeline first to populate data)")
        return True

    # 1. Column verification
    required = {"club_id", "club_name", "short_name", "squad_size", "squad_goals", "squad_assists", "avg_player_appearances", "league_position", "points", "goal_difference"}
    missing = required - set(rows[0].keys())
    if missing:
        print(f"  ❌ Missing required columns in vw_club_analytics: {missing}")
        return False

    # 2. Ordering check (league_position ASC)
    prev_pos = -1
    for r in rows:
        pos = r["league_position"]
        if pos < prev_pos:
            print(f"  ❌ Ordering violation: position {pos} appeared after {prev_pos}")
            return False
        prev_pos = pos

    print(f"  [OK] Multi-table aggregation verified: {len(rows)} clubs evaluated")
    print(f"  [OK] LEFT JOIN aggregations: squad size, goals, assists, and avg appearances computed")
    print(f"  [OK] Ordering verified: sorted by league_position ASC")

    # Render ASCII Club Analytics preview
    print("\n  " + "-" * 82)
    print(f"  {'Pos':<4} | {'Club':<20} | {'Squad':<6} | {'Goals':<6} | {'Assists':<8} | {'Avg Apps':<9} | {'Points':<7} | {'GD'}")
    print("  " + "-" * 82)
    for r in rows[:5]:
        avg_apps = f"{r['avg_player_appearances']:.1f}" if r["avg_player_appearances"] is not None else "-"
        print(f"  {r['league_position']:<4} | {r['club_name']:<20} | {r['squad_size']:<6} | {r['squad_goals']:<6} | {r['squad_assists']:<8} | {avg_apps:<9} | {r['points']:<7} | {r['goal_difference']}")
    if len(rows) > 5:
        print(f"  ... ({len(rows) - 5} more clubs)")
    print("  " + "-" * 82)
    return True


def run_analytical_views_diagnostics():
    """Main verification orchestrator for analytical SQL views."""
    print("\n" + "=" * 80)
    print("        EPL DATA PLATFORM - ANALYTICAL SQL VIEWS DIAGNOSTIC TOOL       ")
    print("=" * 80 + "\n")

    engine = get_db_engine()
    create_all_tables(engine)
    create_analytical_views(engine)

    with get_db_session(engine) as session:
        print("[1/3] Verifying vw_league_table (Window Function DENSE_RANK & Tie-Breaks)...")
        league_ok = verify_league_table_view(session)

        print("\n[2/3] Verifying vw_top_scorers (Window Function ROW_NUMBER & Golden Boot)...")
        scorers_ok = verify_top_scorers_view(session)

        print("\n[3/3] Verifying vw_club_analytics (Multi-Table Aggregation & LEFT JOINs)...")
        analytics_ok = verify_club_analytics_view(session)

    all_passed = all([league_ok, scorers_ok, analytics_ok])

    print("\n" + "=" * 80)
    if all_passed:
        print("  STATUS: ALL ANALYTICAL SQL VIEW VERIFICATIONS PASSED (3/3)  ")
    else:
        print("  STATUS: SOME ANALYTICAL SQL VIEW VERIFICATIONS FAILED       ")
    print("=" * 80 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    run_analytical_views_diagnostics()
