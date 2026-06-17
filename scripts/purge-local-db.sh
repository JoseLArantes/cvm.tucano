#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_SERVICE="${DB_SERVICE:-cvm_postgres}"
DB_NAME="${DB_NAME:-cvm}"
DB_USER="${DB_USER:-cvm}"
STOP_WRITERS="${STOP_WRITERS:-1}"

usage() {
  cat <<'EOF'
Usage:
  scripts/purge-local-db.sh --yes

Purges all application data from the local Docker Compose Postgres database.
Keeps schema and alembic_version. Truncates every other public table, including usuarios.

Environment overrides:
  DB_SERVICE=cvm_postgres
  DB_NAME=cvm
  DB_USER=cvm
  STOP_WRITERS=0
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" != "--yes" && "${PURGE_LOCAL_DB_CONFIRM:-}" != "YES" ]]; then
  usage
  echo
  echo "Refusing to purge without --yes or PURGE_LOCAL_DB_CONFIRM=YES."
  exit 2
fi

cd "$ROOT_DIR"

if [[ ! -f docker-compose.yml ]]; then
  echo "docker-compose.yml not found from $ROOT_DIR."
  exit 1
fi

echo "Checking local database service: $DB_SERVICE"
docker compose exec -T "$DB_SERVICE" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null

if [[ "$STOP_WRITERS" == "1" ]]; then
  echo "Stopping local writer services: cvm_worker cvm_scheduler"
  docker compose stop cvm_worker cvm_scheduler >/dev/null
fi

echo "Flushing Redis cache and task queues..."
docker compose exec -T cvm_redis redis-cli flushall >/dev/null

echo "Purging all database data (dropping and recreating schema 'public') from database: $DB_NAME"
docker compose exec -T "$DB_SERVICE" psql -U "$DB_USER" -d "$DB_NAME" <<SQL
\set ON_ERROR_STOP on
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO "$DB_USER";
GRANT ALL ON SCHEMA public TO public;
COMMENT ON SCHEMA public IS 'standard public schema';
SQL

echo "Local database purged."
if [[ "$STOP_WRITERS" == "1" ]]; then
  echo "Writer services remain stopped. Restart with: docker compose up -d cvm_worker cvm_scheduler"
fi
