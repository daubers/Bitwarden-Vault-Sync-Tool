# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A one-way sync tool: reads items out of a Bitwarden vault and writes them into a HashiCorp Vault KV v2 secrets engine. `src/bitwardensync/`, packaged with `uv` (src layout, `hatchling` backend).

## Commands

```
uv sync                     # install deps
uv run bitwardensync        # run the sync
uv run bitwardensync --dry-run              # show what would change, no writes
uv run bitwardensync --on-conflict vault    # keep Vault's value on conflict instead of Bitwarden's
uv run pytest                # run all tests
uv run pytest tests/test_vault.py::test_write_secret_posts_data   # run a single test
```

No lint/format tooling is configured yet.

### Local dev stack

`docker compose up -d` brings up a dev-mode Vault (`localhost:8200`, root
token `root`) and a self-hosted Vaultwarden (Bitwarden-compatible server) at
`https://localhost:8443` (self-signed cert), auto-seeded with a demo account
and 3 sample login items. See the README's "Local dev stack" section for the
full breakdown of what each compose service does (`tls-certs`, `seed`,
`bw-cli`) and how to fetch a personal API key from the seeded account. This is
the only way to exercise the code against something real — there's no mocked
local server otherwise.

## Architecture

Both Bitwarden and Vault are talked to **directly over HTTP** (`requests`) —
deliberately, not by shelling out to the `bw` or `vault` CLIs. That decision
was explicit (see git history): wrapping an external CLI was considered
fragile and an extra install dependency.

- **`bitwarden.py`** — `BitwardenClient.list_items()` authenticates via
  OAuth2 `client_credentials` grant (personal API key: `BW_CLIENTID` looks
  like `user.<uuid>`, `BW_CLIENTSECRET`), then calls `/api/sync`. The vault is
  end-to-end encrypted client-side, so the server never sees the master
  password — decryption happens locally using `crypto.py`.
- **`crypto.py`** — Reimplements Bitwarden's client-side crypto from scratch:
  KDF (PBKDF2-SHA256 or Argon2id, both supported since real accounts use
  either), HKDF-Expand key stretching, and AES-256-CBC + HMAC-SHA256
  `EncString` decryption. Only personal (non-organization) items are
  decrypted — org items are skipped, since unwrapping an org key needs the
  account's RSA keypair, which isn't implemented.
- **`vault.py`** — `VaultClient` manages a KV v2 mount: `kv2_mount_exists()` /
  `ensure_kv2_mount()` (needs `sys/mounts`, a much more privileged capability
  than a typical scoped write token has — see `VaultPermissionError`),
  `read_secret()`, `write_secret()` (create/update; Vault auto-versions).
- **`sync.py`** — Orchestrates the two: for each Bitwarden item, reads the
  current Vault value first and skips the write if it already matches (no
  spurious new Vault versions). On a genuine conflict, Bitwarden wins by
  default; `on_conflict="vault"` leaves Vault untouched and just logs it.
  `ensure_kv2_mount()` failing with `VaultPermissionError` is treated as
  non-fatal (warn and proceed) since a token scoped to just `<mount>/data/*`
  can still write successfully even though it can't check/create the mount.
- **`config.py`** — All configuration is env vars (`Config.from_env()`), no
  config file. See `.env.example` for the full list.

## Testing approach

Tests avoid any live dependency (no `bw` CLI, no running Vault/Vaultwarden)
by mocking `requests.Session.get/post`. `tests/test_crypto.py` and
`tests/test_bitwarden.py` use *real* API payloads captured from the local
Vaultwarden dev stack as fixtures — the crypto path is exercised against
genuine ciphertext, not synthetic data, so it's an actual regression test of
the decryption algorithm, not just a mock-plumbing check. When adding
Bitwarden-side tests, prefer this pattern (capture a real payload from the
local stack, hardcode it as a fixture) over hand-constructing encrypted
fixtures.
