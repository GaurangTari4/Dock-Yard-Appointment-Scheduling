"""Verify a generated baseline against its manifest and core database invariants."""
import argparse
import json
import os
import sys
from pathlib import Path

import psycopg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    checks: list[tuple[str, bool, str]] = []
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for table, expected in manifest["row_counts"].items():
            cur.execute(f"SELECT count(*) FROM {table}")
            actual = cur.fetchone()[0]
            checks.append((f"row_count.{table}", actual == expected, f"{actual} expected {expected}"))
        cur.execute("SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated")
        checks.append(("foreign_keys_validated", cur.fetchone()[0] == 0, "all foreign keys validated"))
        cur.execute("""SELECT count(*) FROM dock_reservations a JOIN dock_reservations b
            ON a.dock_id=b.dock_id AND a.dock_reservation_id<b.dock_reservation_id
            AND a.start_ts<b.end_ts AND b.start_ts<a.end_ts""")
        checks.append(("dock_overlaps", cur.fetchone()[0] == 0, "no baseline overlaps"))
        cur.execute("""SELECT count(*) FROM (SELECT appointment_id, bool_and(event_ts >= prior) ordered
            FROM (SELECT appointment_id,event_ts,lag(event_ts) OVER (PARTITION BY appointment_id ORDER BY sequence_no) prior FROM operational_events) q
            GROUP BY appointment_id HAVING bool_and(event_ts >= prior) IS FALSE) bad""")
        checks.append(("event_order", cur.fetchone()[0] == 0, "events nondecreasing by sequence"))
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
    return 0 if all(passed for _, passed, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
