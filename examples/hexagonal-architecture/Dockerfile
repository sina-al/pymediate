# One Dockerfile, three images: the APP build argument picks which composition root
# gets installed, and uv's --package flag installs only that package's dependency
# closure. The postgres image contains no Neo4j driver, the neo4j image no psycopg,
# the memory image neither — dependency isolation comes from the package graph, not
# from careful copying.
ARG APP=shop-memory

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ARG APP
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# Build the venv at the same absolute path it will live at in the final image, so the
# entry-point shebangs stay valid after the copy.
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/ apps/
RUN uv sync --frozen --no-dev --no-editable --package "${APP}"

FROM python:3.12-slim-bookworm
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Every variant ships the same entry points (shop-web, shop, and — except the memory
# variant — shop-worker); compose overrides the command for worker containers.
CMD ["shop-web"]
