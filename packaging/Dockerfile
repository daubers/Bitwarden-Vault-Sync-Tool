# Builder image for the .deb package. Debian bookworm (not trixie) is used
# deliberately: a self-contained runtime built against bookworm's glibc will
# also run on newer releases (trixie and later), but the reverse isn't true.
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl dpkg-dev && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /src
ENTRYPOINT ["packaging/build-in-container.sh"]
