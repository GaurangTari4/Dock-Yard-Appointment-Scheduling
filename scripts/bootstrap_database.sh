#!/bin/sh
# Initialize an empty local Compose database. Existing data is never replaced.
set -eu

profile="${DATASET_PROFILE:-tiny}"
seed="${DATASET_SEED:-20261022}"
case "$profile" in tiny|starter|full) ;; *) echo "Unsupported DATASET_PROFILE: $profile" >&2; exit 2;; esac

export PGPASSWORD="${POSTGRES_PASSWORD:-}"
for attempt in $(seq 1 60); do
  pg_isready -h postgres -U logistics -d logistics >/dev/null 2>&1 && break
  [ "$attempt" = 60 ] && { echo "PostgreSQL readiness timed out" >&2; exit 1; }
  sleep 1
done

populated="$(psql -h postgres -U logistics -d logistics -Atc "SELECT to_regclass('public.facilities') IS NOT NULL AND (SELECT count(*) FROM facilities) > 0" 2>/dev/null || true)"
if [ "$populated" = "t" ]; then
  echo "Database already populated; preserving it without reload. Remove only this Compose project's volumes explicitly to change profiles."
  exit 0
fi

psql -q -v ON_ERROR_STOP=1 -h postgres -U logistics -d logistics -f /app/database/schema.sql
alembic upgrade head
output="/generated/${profile}"
python -m src.generator --profile "$profile" --seed "$seed" --output "$output"
psql -q -v ON_ERROR_STOP=1 -h postgres -U logistics -d logistics -f "$output/baseline/seed_data.sql"
python /app/scripts/verify_loaded_dataset.py --manifest "$output/baseline/manifest.json"
echo "Loaded deterministic ${profile} baseline (seed ${seed})"
