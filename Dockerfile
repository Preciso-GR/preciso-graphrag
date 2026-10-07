# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3

FROM ${PYTHON_IMAGE} AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
WORKDIR /build
COPY requirements.lock requirements-build.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --require-hashes --only-binary=:all: -r requirements-build.lock && \
    python -m venv --without-pip /opt/venv && \
    python -m pip --python /opt/venv/bin/python install --require-hashes --only-binary=:all: -r requirements.lock
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN python -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels . && \
    python -m pip --python /opt/venv/bin/python install --no-deps /wheels/*.whl && \
    /opt/venv/bin/python -c "import tiktoken; tiktoken.encoding_for_model('gpt-4o-mini')"

FROM builder AS test
COPY requirements-dev.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip --python /opt/venv/bin/python install --require-hashes --only-binary=:all: -r requirements-dev.lock
COPY tests ./tests
COPY scripts ./scripts
COPY pytest.ini ./
RUN /opt/venv/bin/python -m pytest -q && \
    /opt/venv/bin/python -m ruff check src tests scripts && \
    /opt/venv/bin/python tests/manual/summary_merge_manual.py && \
    /opt/venv/bin/python tests/manual/marker_leak_manual.py

FROM ${PYTHON_IMAGE} AS runtime
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache \
    GRAPHRAG_MCP_WORKDIR=/data/graph \
    GRAPHRAG_INPUT_DIR=/inputs \
    GRAPHRAG_STRICT_SOURCE_IDS=true \
    HOME=/tmp
RUN groupadd --gid 10001 preciso && \
    useradd --uid 10001 --gid preciso --no-create-home --shell /usr/sbin/nologin preciso && \
    mkdir -p /app /data/graph /inputs && \
    chown -R preciso:preciso /data && \
    python -m pip uninstall --yes pip
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/tiktoken-cache /opt/tiktoken-cache
USER 10001:10001
WORKDIR /app
ENTRYPOINT ["python", "-m", "preciso_mcp.server"]
