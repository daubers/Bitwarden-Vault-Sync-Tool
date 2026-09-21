# BitwardenSync

Syncs secrets from Bitwarden into a HashiCorp Vault KV store.

## Layout

```
src/bitwardensync/
    cli.py       # entry point (`bitwardensync` console script)
    config.py    # env-var configuration
    crypto.py    # Bitwarden's client-side vault crypto (KDF, EncString decryption)
    bitwarden.py # Bitwarden client (talks to the API directly, no `bw` CLI)
    vault.py     # Vault KV v2 client (talks to Vault's HTTP API directly)
    sync.py      # sync orchestration
tests/
```

## Setup

```
uv sync
cp .env.example .env   # fill in credentials
```

## Local dev stack

`docker-compose.yml` brings up a local Vault (dev mode) and a Vaultwarden
instance (self-hosted, Bitwarden-client-compatible server), pre-populated with
a demo account and sample login items, to build and test against — nothing
here talks to production Bitwarden or Vault:

```
docker compose up -d
```

This starts:

- **vault** — dev-mode Vault at http://localhost:8200, root token `root`
  (unsealed, in-memory, not for real secrets). The `secret/` KV v2 engine is
  enabled automatically.
- **tls-certs** — one-shot job that generates a self-signed cert into the
  `vaultwarden-tls` volume. Vaultwarden's web-vault UI refuses to run over
  plain HTTP even for local dev, so vaultwarden serves HTTPS using it.
- **vaultwarden** — self-hosted Bitwarden-compatible server at
  https://localhost:8443 (self-signed cert — accept the browser warning).
- **seed** — one-shot job that registers a demo account (via the actual
  web-vault UI, since Bitwarden's registration crypto happens client-side and
  can't be done with a plain API call) and creates 3 sample login items. Safe
  to rerun: it skips registration/items that already exist, so plain
  `docker compose up -d` on an existing stack is a no-op here.

Demo account (overridable via `SEED_EMAIL`/`SEED_PASSWORD`/`SEED_NAME` env
vars, or in `.env`):

- Email: `demo@example.com`
- Password: `SeedMasterPassw0rd!123`

Check `docker compose logs seed` if you want to confirm it finished; it
usually takes 10-20s after vaultwarden becomes healthy.

`.env.example` already points VAULT_ADDR/VAULT_TOKEN at this local stack by
default. To point `bitwardensync` itself at the seeded Vaultwarden account,
open https://localhost:8443, log in with the demo credentials above, and
generate a personal API key under Account Settings > Security > Keys to get
`BW_CLIENTID` (looks like `user.<uuid>`) and `BW_CLIENTSECRET`. Set
`BW_SERVER_URL=https://localhost:8443` too, since that's a self-hosted
instance rather than the official bitwarden.com.

`bitwardensync` talks to the Bitwarden API directly (see `bitwarden.py` /
`crypto.py`) rather than shelling out to the `bw` CLI, so nothing extra needs
to be installed to run it. The `bw-cli` compose service below is just a
convenience for poking at the local Vaultwarden by hand — not something
`bitwardensync` itself uses. To run ad-hoc `bw` CLI commands against the local
Vaultwarden without installing the CLI locally (config/session persist across
runs in the `bw-cli-data` volume, so `config server` only needs to happen
once):

```
docker compose run --rm bw-cli bw config server https://vaultwarden:80
docker compose run --rm bw-cli bw login demo@example.com
docker compose run --rm bw-cli bw sync
```

Tear down (and wipe volumes, including the seeded account) with:

```
docker compose down -v
```

## Usage

```
uv run bitwardensync              # sync Bitwarden -> Vault
uv run bitwardensync --dry-run    # show what would change, without writing
```

For each Bitwarden item, `bitwardensync` reads the current value at its Vault
path first and skips the write entirely if it already matches — so a synced-up
vault produces no new secret versions. If Vault has a different value at that
path (e.g. someone edited it by hand), Bitwarden's version wins by default and
overwrites it; pass `--on-conflict vault` to leave Vault's version alone
instead and just log the conflict.

## Configuration

Set via environment variables (see `.env.example`):

- `BW_CLIENTID`, `BW_CLIENTSECRET`, `BW_PASSWORD` - Bitwarden API credentials
- `VAULT_ADDR`, `VAULT_TOKEN` - Vault connection
- `VAULT_MOUNT` - KV mount point (default `secret`)
- `VAULT_PATH_PREFIX` - path prefix under the mount for synced secrets (default `bitwarden`)

### Vault permissions

`bitwardensync` checks whether `VAULT_MOUNT` exists as a KV v2 engine and
creates it if not — but that check requires `sys/mounts` access, which is a
more privileged, cluster-wide capability than most deployments want to hand
out. A token scoped only to `<mount>/data/*` (the common least-privilege
setup, e.g. a policy like `path "secret/data/*" { capabilities = ["create",
"update"] }`) can still write/update secrets just fine; it just can't verify
or create the mount itself. When that's the case, `run_sync` prints a warning
and proceeds with the writes rather than failing — if the mount genuinely
doesn't exist, the writes will fail with their own clear error instead.

## Tests

```
uv run pytest
```

## Linting

[Ruff](https://docs.astral.sh/ruff/) handles both linting and formatting; it
is configured in `pyproject.toml` (100-column lines, targeting Python 3.13).

```
uv run ruff check .          # lint
uv run ruff check --fix .    # lint and apply safe autofixes
uv run ruff format .         # format
```

CI runs `ruff check` and `ruff format --check` as a separate job alongside the
tests, so unformatted code fails the build.

## Debian package

`bitwardensync` requires Python >= 3.13 and dependency versions newer than
what current Debian stable ships, so the `.deb` is fully self-contained: it
bundles its own Python 3.13 base interpreter (a relocatable
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)
build, at `/opt/bitwardensync/python`) with a proper venv on top of it
(`/opt/bitwardensync/venv`, holding bitwardensync and its dependencies —
nothing is installed outside a venv), and `/usr/bin/bitwardensync` symlinked
into it. No system Python or matching library versions are required on the
target host. Configuration is still via environment variables (see
`.env.example`, also installed to `/usr/share/doc/bitwardensync/env.example`)
— the package doesn't install a systemd unit, so wire it up to cron/systemd
yourself.

Build it (requires Docker; the actual build runs inside a Debian container,
so this works from any host OS/arch):

```
packaging/build.sh                  # native platform (fastest)
packaging/build.sh linux/amd64      # cross-build for amd64
```

Cross-building depends on QEMU user-mode emulation for foreign
architectures, which can be flaky for `uv`/Rust binaries (seen: segfaults
under `linux/amd64` emulation on an Apple Silicon host). If a cross-build
fails, build natively on a machine of the target architecture instead (e.g.
an amd64 CI runner).

Output lands in `dist/bitwardensync_<version>_<arch>.deb`. Install/remove
with the usual:

```
sudo dpkg -i dist/bitwardensync_0.1.0_amd64.deb
sudo dpkg -r bitwardensync
```

### Package feed

The Gitea Actions workflow (`.gitea/workflows/build-deb.yml`) builds the
`.deb` on every push/PR and uploads it as a workflow artifact; on pushes to
`main` it also publishes to the `main` feed on the self-hosted ProGet
instance at `pkgs.daubney.dev` (distribution `stable`, component `main`),
using the `PKGS_USER`/`PKGS_PASSWORD` repo secrets. To install from it:

The feed requires HTTP Basic Auth for reads too (ProGet's free edition
doesn't support anonymous/GPG-signed feeds), so both a sources list entry
and an `apt` auth config are needed:

```
echo "deb [trusted=yes] https://pkgs.daubney.dev/debian/main stable main" | sudo tee /etc/apt/sources.list.d/bitwardensync.list
sudo tee /etc/apt/auth.conf.d/bitwardensync.conf <<EOF
machine pkgs.daubney.dev login <PKGS_USER> password <PKGS_PASSWORD>
EOF
sudo chmod 600 /etc/apt/auth.conf.d/bitwardensync.conf
sudo apt update
sudo apt install bitwardensync
```

(`trusted=yes` skips GPG signature verification — the feed isn't
GPG-signed.)

## License

BSD 3-Clause. See [LICENSE](LICENSE).
