#!/usr/bin/env bash
# Launch instagram-bulk-downloader - keeps the repo root clean.
#   ./run.sh <username> --login-user you [--limit N]
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PY="${PYTHON:-python3}"
exec "$PY" -m app.main "$@"
