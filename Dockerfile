# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    ZEBRAMOTIF_HOST=0.0.0.0 \
    ZEBRAMOTIF_PORT=8568 \
    ZEBRAMOTIF_DATA_DIR=/var/lib/zebramotif/datasets/0.1 \
    MPLCONFIGDIR=/tmp/zebramotif-matplotlib

WORKDIR /app

RUN groupadd --gid 10001 zebramotif \
    && useradd --uid 10001 --gid zebramotif --create-home zebramotif \
    && mkdir -p /var/lib/zebramotif/datasets \
    && chown -R zebramotif:zebramotif /var/lib/zebramotif

# Install locked dependencies in a layer that survives application edits.
COPY pyproject.toml uv.lock README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY notices/ ./notices/
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable --no-cache
# COPY applies this mode to newly created parent directories too.
COPY --chmod=0755 deploy/start.sh ./deploy/start.sh

USER 10001:10001
# Check access as the runtime user before an image can reach production.
RUN bash -n deploy/start.sh \
    && .venv/bin/python -m zebramotif.dataset --help > /dev/null
EXPOSE 8568

# The dataset lives on a persistent volume; credentials are supplied at runtime.
CMD ["bash", "deploy/start.sh"]
