# Builder image for the .deb package. Debian bookworm (not trixie) is used
# deliberately: a self-contained runtime built against bookworm's glibc will
# also run on newer releases (trixie and later), but the reverse isn't true.
#
# Multi-stage on purpose: the build runs entirely at `docker build` time
# (source copied in via COPY, not a `docker run -v` bind mount), and the
# result is extracted with BuildKit's `--output type=local` rather than
# `docker cp`. A runtime bind mount needs a path that exists on whichever
# daemon actually runs the container, which breaks under docker-outside-of-
# docker (common on CI runners, where the job itself runs in a container and
# talks to the *host's* daemon) — `docker build`'s context and `--output`
# are both streamed over the API instead, so neither cares about that.
FROM debian:bookworm-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl dpkg-dev && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /src
COPY . .
RUN packaging/build-in-container.sh

FROM scratch AS export
COPY --from=builder /src/dist/*.deb /
