#!/usr/bin/env bash
# Builds the bitwardensync .deb package. Runs the actual build inside a
# Debian container (see packaging/Dockerfile) so it works regardless of the
# host OS/arch, and so the bundled runtime is a genuine Linux build. Output
# lands in dist/bitwardensync_<version>_<arch>.deb.
#
# Targets the Docker daemon's native platform by default (fastest). Pass a
# platform to cross-build instead, e.g.:
#   packaging/build.sh linux/amd64
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PLATFORM_ARGS=()
if [ "$#" -gt 0 ]; then
    PLATFORM_ARGS=(--platform "$1")
fi

mkdir -p dist
docker build "${PLATFORM_ARGS[@]+"${PLATFORM_ARGS[@]}"}" \
    --target export --output type=local,dest=dist \
    -f packaging/Dockerfile .
