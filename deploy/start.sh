#!/usr/bin/env bash
# Container entrypoint: prepare a persistent dataset before starting website workers.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
app_python="${ZEBRAMOTIF_PYTHON:-.venv/bin/python}"

# Reads a mounted secret or environment variable only on an empty cache. A complete
# cache is verified and reused, including when the share link has expired/revoked.
"$app_python" -m zebramotif.dataset

# Website workers need only ZEBRAMOTIF_DATA_DIR, never Zenodo credentials.
unset ZEBRAMOTIF_ZENODO_URL ZEBRAMOTIF_ZENODO_URL_FILE
exec "$app_python" -m gunicorn zebramotif.app:server \
    --bind "${ZEBRAMOTIF_HOST:-127.0.0.1}:${ZEBRAMOTIF_PORT:-8568}" \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
