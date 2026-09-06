# syntax=docker/dockerfile:1
FROM rust:1.98-slim-bookworm AS rust
FROM python:3.13-slim-bookworm AS build
COPY --from=rust /usr/local/cargo /usr/local/cargo
COPY --from=rust /usr/local/rustup /usr/local/rustup
ENV PATH="/usr/local/cargo/bin:${PATH}" RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir maturin==1.15.0
WORKDIR /build
COPY Cargo.toml Cargo.lock pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY python/rushstats/*.py python/rushstats/*.pyi python/rushstats/py.typed python/rushstats/
RUN maturin build --release --locked --strip --interpreter python --out /wheels

FROM python:3.13-slim-bookworm AS runtime
LABEL org.opencontainers.image.title="rushstats" \
      org.opencontainers.image.description="Rust-powered CSV statistics and Markdown reports" \
      org.opencontainers.image.source="https://github.com/jan-klacan/rushstats" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /wheels/ /wheels/
RUN python -m pip install --no-cache-dir --no-deps /wheels/*.whl \
    && rm -rf /wheels \
    && mkdir /data && chown 10001:10001 /data
WORKDIR /data
USER 10001:10001
ENTRYPOINT ["rushstats"]
CMD ["--help"]
