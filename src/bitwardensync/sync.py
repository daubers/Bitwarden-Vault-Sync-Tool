from __future__ import annotations

import sys
from typing import Literal

from bitwardensync.bitwarden import BitwardenClient
from bitwardensync.config import Config
from bitwardensync.vault import VaultClient, VaultPermissionError

OnConflict = Literal["bitwarden", "vault"]


def run_sync(
    config: Config,
    on_conflict: OnConflict = "bitwarden",
    dry_run: bool = False,
) -> None:
    bitwarden = BitwardenClient(
        client_id=config.bw_client_id,
        client_secret=config.bw_client_secret,
        password=config.bw_password,
        server_url=config.bw_server_url,
    )
    vault = VaultClient(
        addr=config.vault_addr,
        token=config.vault_token,
        mount=config.vault_mount,
    )

    try:
        vault.ensure_kv2_mount()
    except VaultPermissionError as error:
        # A token scoped only to `<mount>/data/*` (common for least-privilege
        # setups) can still write secrets even though it can't check/create
        # the mount itself, so this isn't necessarily fatal.
        print(
            f"Warning: {error} Assuming it already exists and continuing.",
            file=sys.stderr,
        )

    for item in bitwarden.list_items():
        path = f"{config.vault_path_prefix}/{item.name}"
        existing = vault.read_secret(path)

        if existing == item.fields:
            print(f"up to date, skipping: {path}")
            continue

        if existing is not None and on_conflict == "vault":
            print(
                f"conflict at {path}: Bitwarden and Vault differ; "
                "keeping Vault's version (--on-conflict=vault)",
                file=sys.stderr,
            )
            continue

        verb = "update" if existing is not None else "create"
        if dry_run:
            print(f"would {verb}: {path}")
            continue

        vault.write_secret(path, item.fields)
        print(f"{verb}d: {path}")
