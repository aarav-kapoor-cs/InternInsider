#!/bin/bash
# Starts the InternInsider backend on a Mac with Homebrew PostgreSQL.
# Safe to run again and again.   Usage:  bash start-backend.sh
cd "$(dirname "$0")/backend" || exit 1
# Copy everything this script prints into backend.log (handy for debugging).
exec > >(tee ../backend.log) 2>&1
PG=/opt/homebrew/opt/postgresql@16/bin
SQL() { "$PG/psql" -h localhost -U postgres -d "$1" -tAc "$2"; }

# 1. Make sure PostgreSQL is running.
if ! "$PG/pg_isready" -q -h localhost -p 5432; then
  echo "Starting PostgreSQL..."
  brew services start postgresql@16
  sleep 3
fi
if ! "$PG/pg_isready" -q -h localhost -p 5432; then
  echo "ERROR: PostgreSQL is not answering on port 5432. Run: brew services restart postgresql@16"
  exit 1
fi

# 2. Create the 'postgres' user and the database (ignored if they already exist).
"$PG/createuser" -h localhost -s postgres 2>/dev/null
"$PG/createdb" -h localhost interninsider 2>/dev/null

# 3. pgvector. If the extension can't be turned on, build it once from source.
if ! SQL interninsider "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null 2>&1; then
  MAJOR=$(SQL postgres "SELECT current_setting('server_version_num')::int / 10000")
  PG_CONFIG=/opt/homebrew/opt/postgresql@$MAJOR/bin/pg_config
  echo "Installing pgvector for PostgreSQL $MAJOR (one time, about a minute)..."
  TMP=$(mktemp -d)
  git clone -q --depth 1 --branch v0.8.0 https://github.com/pgvector/pgvector.git "$TMP/pgvector" \
    && make -C "$TMP/pgvector" PG_CONFIG="$PG_CONFIG" >/dev/null \
    && make -C "$TMP/pgvector" install PG_CONFIG="$PG_CONFIG" >/dev/null
  if ! SQL interninsider "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null; then
    echo "ERROR: could not install pgvector. Copy the lines above to Claude."
    exit 1
  fi
fi

# 4. Tesseract, the OCR engine used for scanned resumes.
command -v tesseract >/dev/null || { echo "Installing Tesseract OCR (one time)..."; brew install tesseract; }

# 5. Python virtual environment + packages.
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q -r requirements.txt || { echo "ERROR: pip install failed"; exit 1; }

# 6. Settings file for your API key.
[ -f .env ] || cp .env.example .env

# 7. Load the job postings the first time (downloads the embedding model once).
#    Uses the saved LinkedIn snapshot if there is one, otherwise the invented sample postings.
COUNT=$(SQL interninsider "SELECT count(*) FROM jobs" 2>/dev/null)
if [ -z "$COUNT" ] || [ "$COUNT" = "0" ]; then
  echo "Loading job postings (first run downloads a small embedding model)..."
  if [ -f data/linkedin_jobs.json ]; then
    python -m app.ingest --linkedin --cached || { echo "ERROR: loading jobs failed"; exit 1; }
  else
    python -m app.ingest || { echo "ERROR: loading jobs failed"; exit 1; }
    echo "Loaded SAMPLE postings. For real ones run: cd backend && python -m app.ingest --linkedin"
  fi
fi

# 8. Run the server.
echo "Backend starting on http://localhost:8001  (Ctrl+C to stop)"
exec python -m uvicorn app.main:app --reload --port 8001
