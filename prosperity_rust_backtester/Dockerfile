FROM rust:1.88-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-dev python3-pip make ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYO3_PYTHON=python3

WORKDIR /app

COPY Cargo.toml Cargo.lock pyproject.toml Makefile README.md LICENSE-APACHE LICENSE-MIT ./
COPY src ./src
COPY scripts ./scripts
COPY datasets ./datasets
COPY traders ./traders

RUN cargo build --release

RUN /app/target/release/rust_backtester --products off > /tmp/smoke_output.txt

CMD ["/app/target/release/rust_backtester"]
