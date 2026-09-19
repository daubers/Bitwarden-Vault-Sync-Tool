#!/usr/bin/env bash
# Runs inside the packaging/Dockerfile builder image (see packaging/build.sh).
# Produces a self-contained .deb: bundles a relocatable CPython 3.13 build
# (via `uv python install`, which fetches python-build-standalone releases)
# plus a venv on top of it with bitwardensync and all its dependencies
# installed. Nothing on the target host's system Python is required, and
# nothing is installed outside a venv (no --break-system-packages).
set -euo pipefail

SRC_DIR="/src"
WORK_DIR="/tmp/build"
PKG_ROOT="${WORK_DIR}/pkgroot"
ARCH="$(dpkg --print-architecture)"

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "${SRC_DIR}/pyproject.toml" | head -1)"
if [ -z "${VERSION}" ]; then
    echo "error: could not read version from pyproject.toml" >&2
    exit 1
fi

rm -rf "${WORK_DIR}"
mkdir -p "${PKG_ROOT}/opt/bitwardensync" "${PKG_ROOT}/usr/bin" \
         "${PKG_ROOT}/usr/share/doc/bitwardensync" "${PKG_ROOT}/DEBIAN"

export UV_PYTHON_INSTALL_DIR="${WORK_DIR}/uv-python"
uv python install 3.13

PYTHON_BIN="$(readlink -f "$(uv python find 3.13)")"
RUNTIME_SRC="$(dirname "$(dirname "${PYTHON_BIN}")")"

# Copy the base interpreter into the package tree first, then build the venv
# from that copy — building the venv against the pre-copy (uv cache) path and
# relocating afterwards would leave stale absolute paths baked into
# pyvenv.cfg and the bin/ symlinks.
cp -a "${RUNTIME_SRC}" "${PKG_ROOT}/opt/bitwardensync/python"
BASE_PYTHON="${PKG_ROOT}/opt/bitwardensync/python/bin/python3.13"

uv venv --python "${BASE_PYTHON}" "${PKG_ROOT}/opt/bitwardensync/venv"
uv build --wheel --out-dir "${WORK_DIR}/dist" "${SRC_DIR}"
uv pip install --python "${PKG_ROOT}/opt/bitwardensync/venv/bin/python3.13" "${WORK_DIR}"/dist/bitwardensync-*.whl

# Everything above was built under the build-time PKG_ROOT path; rewrite the
# baked-in absolute references (pyvenv.cfg, the venv's python symlinks, the
# console-script shebang, activate scripts) to the package's final,
# deployed location.
sed -i "s|${PKG_ROOT}||g" "${PKG_ROOT}/opt/bitwardensync/venv/pyvenv.cfg" "${PKG_ROOT}/opt/bitwardensync/venv/bin/activate"*
sed -i "1s|^#!.*|#!/opt/bitwardensync/venv/bin/python3.13|" "${PKG_ROOT}/opt/bitwardensync/venv/bin/bitwardensync"
for link in "${PKG_ROOT}/opt/bitwardensync/venv/bin/python3.13" "${PKG_ROOT}/opt/bitwardensync/venv/bin/python3" "${PKG_ROOT}/opt/bitwardensync/venv/bin/python"; do
    if [ -L "${link}" ]; then
        ln -sf /opt/bitwardensync/python/bin/python3.13 "${link}"
    fi
done

# Precompile bytecode so it ships as tracked package content instead of
# being written (and left behind on purge) the first time it's run.
"${BASE_PYTHON}" -m compileall -q "${PKG_ROOT}/opt/bitwardensync"

ln -s /opt/bitwardensync/venv/bin/bitwardensync "${PKG_ROOT}/usr/bin/bitwardensync"
install -m 644 "${SRC_DIR}/.env.example" "${PKG_ROOT}/usr/share/doc/bitwardensync/env.example"
install -m 644 "${SRC_DIR}/README.md" "${PKG_ROOT}/usr/share/doc/bitwardensync/README.md"
gzip -n -9 -c "${SRC_DIR}/packaging/debian/changelog" > "${PKG_ROOT}/usr/share/doc/bitwardensync/changelog.gz"
install -m 644 "${SRC_DIR}/packaging/debian/copyright" "${PKG_ROOT}/usr/share/doc/bitwardensync/copyright"

INSTALLED_SIZE="$(du -sk --exclude=DEBIAN "${PKG_ROOT}" | cut -f1)"
sed -e "s/@VERSION@/${VERSION}/" -e "s/@ARCH@/${ARCH}/" -e "s/@INSTALLED_SIZE@/${INSTALLED_SIZE}/" \
    "${SRC_DIR}/packaging/debian/control.in" > "${PKG_ROOT}/DEBIAN/control"

mkdir -p "${SRC_DIR}/dist"
DEB_PATH="${SRC_DIR}/dist/bitwardensync_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "${PKG_ROOT}" "${DEB_PATH}"
echo "built ${DEB_PATH}"
