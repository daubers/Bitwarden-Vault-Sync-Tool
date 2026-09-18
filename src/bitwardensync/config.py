from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bw_client_id: str
    bw_client_secret: str
    bw_password: str
    vault_addr: str
    vault_token: str
    vault_mount: str = "secret"
    vault_path_prefix: str = "bitwarden"
    bw_server_url: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            bw_client_id=_require_env("BW_CLIENTID"),
            bw_client_secret=_require_env("BW_CLIENTSECRET"),
            bw_password=_require_env("BW_PASSWORD"),
            vault_addr=_require_env("VAULT_ADDR"),
            vault_token=_require_env("VAULT_TOKEN"),
            vault_mount=os.environ.get("VAULT_MOUNT", "secret"),
            vault_path_prefix=os.environ.get("VAULT_PATH_PREFIX", "bitwarden"),
            bw_server_url=os.environ.get("BW_SERVER_URL") or None,
        )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
