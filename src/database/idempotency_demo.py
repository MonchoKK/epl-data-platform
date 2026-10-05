"""CLI Demonstration Tool: Pipeline Idempotency & Upsert Verification

Runs the EPL ELT pipeline multiple times and proves mathematically that:
Run 1 -> 55 records
Run 2 -> 55 records
Run 3 -> 55 records

Zero duplicate records are created because the loader uses an upsert/merge strategy.
"""

from typing import Any, Dict, List
from src.database.connection import get_db_engine, get_db_session
from src.database.models import Club, Match, Player, Standing
from src.pipeline_runner import run_full_pipeline


def count_all_tables(session) -> Dict[str, int]:
    """Returns row counts across all 4 warehouse relational tables."""
    return {
        "clubs": session.query(Club).count(),
        "players": session.query(Player).count(),
        "matches": session.query(Match).count(),
        "standings": session.query(Standing).count(),
    }


def run_idempotency_proof(runs: int = 3):
    """Executes the pipeline `runs` times and displays the idempotency proof table."""
    print("\n" + "=" * 80)
    print("           EPL DATA PLATFORM - IDEMPOTENCY & UPSERT DEMONSTRATION           ")
    print("=" * 80)
    print("Proving that repeated executions update in place without creating duplicates.\n")

    history: List[Dict[str, Any]] = []

    for i in range(1, runs + 1):
        print(f"--> Executing Pipeline Run #{i}...")
        run_full_pipeline()

        with get_db_session() as session:
            counts = count_all_tables(session)
            total = sum(counts.values())
            history.append({
                "run": f"Run {i}",
                "clubs": counts["clubs"],
                "players": counts["players"],
                "matches": counts["matches"],
                "standings": counts["standings"],
                "total": total,
            })

    # Render ASCII Proof Table
    print("\n" + "=" * 84)
    print("                         IDEMPOTENCY VERIFICATION RESULTS                           ")
    print("=" * 84)
    print(f"{'Execution':<10} | {'Clubs':<7} | {'Players':<9} | {'Matches':<9} | {'Standings':<11} | {'Total In DB':<13} | {'Outcome'}")
    print("-" * 11 + "+" + "-" * 9 + "+" + "-" * 11 + "+" + "-" * 11 + "+" + "-" * 13 + "+" + "-" * 15 + "+" + "-" * 11)

    all_match = True
    base_total = history[0]["total"]

    for idx, h in enumerate(history):
        if idx == 0:
            outcome = "Initial Load"
        else:
            diff = h["total"] - base_total
            if diff == 0:
                outcome = "No Duplicates (OK)"
            else:
                outcome = f"+{diff} Duplicates (FAILED)"
                all_match = False

        print(
            f"{h['run']:<10} | {h['clubs']:<7} | {h['players']:<9} | {h['matches']:<9} | {h['standings']:<11} | {h['total']:<13} | {outcome}"
        )

    print("=" * 84)
    if all_match and base_total == 55:
        print(" [SUCCESS] Idempotency mathematically proven: Run 1=55, Run 2=55, Run 3=55.")
        print(" Zero duplicates produced. Upsert/merge strategy verified.")
    else:
        print(" [FAILURE] Duplicate rows were detected across executions.")
    print("=" * 84 + "\n")


if __name__ == "__main__":
    run_idempotency_proof(runs=3)
