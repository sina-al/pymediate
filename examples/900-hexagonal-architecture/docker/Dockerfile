# syntax=docker/dockerfile:1.7

ARG UV_IMAGE
ARG PYTHON_IMAGE

FROM ${UV_IMAGE} AS build

ARG SHOP_HOST
ARG SHOP_PROFILE

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /workspace/examples/900-hexagonal-architecture

# The repository root is the build context because this example
# exercises the current PyMediate checkout. Bind mounts retain the repository
# layout expected by the example's local source without copying the raw checkout
# into an intermediate layer. The uv cache is shared by every cloud/host combination.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=examples/900-hexagonal-architecture/uv.lock,target=uv.lock,readonly \
    --mount=type=bind,source=examples/900-hexagonal-architecture/pyproject.toml,target=pyproject.toml,readonly \
    --mount=type=bind,source=examples/900-hexagonal-architecture/packages,target=packages,readonly \
    --mount=type=bind,source=pyproject.toml,target=/workspace/pyproject.toml,readonly \
    --mount=type=bind,source=README.md,target=/workspace/README.md,readonly \
    --mount=type=bind,source=LICENSE,target=/workspace/LICENSE,readonly \
    --mount=type=bind,source=src,target=/workspace/src,readonly \
    uv sync \
        --locked \
        --no-dev \
        --no-editable \
        --extra "${SHOP_HOST}" \
        --extra "${SHOP_PROFILE}"

FROM ${PYTHON_IMAGE} AS runtime

ARG SHOP_PROFILE

# WeasyPrint's Debian runtime libraries and a stable fallback font for the
# invoice and statement renderers.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        fonts-dejavu-core \
        libharfbuzz-subset0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 65532 shop \
    && useradd --uid 65532 --gid shop --no-create-home --shell /usr/sbin/nologin shop

ENV HOME=/tmp \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=build --link /opt/venv /opt/venv
COPY --link examples/900-hexagonal-architecture/configuration/${SHOP_PROFILE}.yaml \
    /etc/shop/configuration.yaml

USER shop
