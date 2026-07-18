ARG PYTHON_VERSION=3.12
FROM mcr.microsoft.com/devcontainers/python:${PYTHON_VERSION}

# WeasyPrint's Debian runtime libraries, plus a deterministic fallback font for
# the branded invoice and statement PDFs. The Python wheel supplies the rest.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        fonts-dejavu-core \
        libharfbuzz-subset0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*
