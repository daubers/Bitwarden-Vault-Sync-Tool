from __future__ import annotations

import requests


class VaultError(RuntimeError):
    """Raised when the Vault API returns an error or unexpected data."""


class VaultPermissionError(VaultError):
    """Raised when the token lacks the `sys/mounts` access needed to check
    or create the mount. This is distinct from other VaultErrors because a
    token scoped only to `<mount>/data/*` (a common least-privilege setup)
    can still successfully call write_secret() even though it can't pass
    this check — callers may want to treat it as non-fatal.
    """


class VaultClient:
    """Manages a HashiCorp Vault KV v2 secrets engine over its HTTP API."""

    def __init__(self, addr: str, token: str, mount: str) -> None:
        self._base_url = addr.rstrip("/")
        self._mount = mount.strip("/")
        self._session = requests.Session()
        self._session.headers["X-Vault-Token"] = token

    def get_mount_info(self) -> dict | None:
        response = self._session.get(f"{self._base_url}/v1/sys/mounts")
        if response.status_code == 403:
            raise VaultPermissionError(
                "No permission to list secrets engines (sys/mounts); "
                "the token needs that access to check whether the "
                f"'{self._mount}/' KV v2 mount exists."
            )
        mounts = _parse_response(response, "list secrets engines")
        return mounts.get(f"{self._mount}/")

    def kv2_mount_exists(self) -> bool:
        info = self.get_mount_info()
        return info is not None and _is_kv2(info)

    def ensure_kv2_mount(self) -> None:
        """Create the configured mount as a KV v2 engine if it doesn't already exist.

        Requires the token to have `sudo`/`sys/mounts` access; raises
        VaultError with a clear message if it doesn't.
        """
        info = self.get_mount_info()
        if info is not None:
            if _is_kv2(info):
                return
            raise VaultError(
                f"Path '{self._mount}/' is already mounted as "
                f"{info.get('type')} (options={info.get('options')}), "
                "not a KV v2 engine"
            )

        response = self._session.post(
            f"{self._base_url}/v1/sys/mounts/{self._mount}",
            json={"type": "kv", "options": {"version": "2"}},
        )
        if response.status_code == 403:
            raise VaultPermissionError(
                f"No permission to create the '{self._mount}/' KV v2 mount; "
                "ask a Vault admin to create it or grant sys/mounts access."
            )
        _parse_response(response, f"create the '{self._mount}/' KV v2 mount")

    def read_secret(self, path: str) -> dict[str, str] | None:
        """Return the latest version's data, or None if it doesn't exist (or
        was soft-deleted)."""
        response = self._session.get(f"{self._base_url}/v1/{self._mount}/data/{path.strip('/')}")
        if response.status_code == 404:
            return None
        body = _parse_response(response, f"read secret at '{path}'")
        return body.get("data", {}).get("data")

    def write_secret(self, path: str, data: dict[str, str]) -> None:
        """Create or update a KV v2 entry; Vault versions it automatically."""
        response = self._session.post(
            f"{self._base_url}/v1/{self._mount}/data/{path.strip('/')}",
            json={"data": data},
        )
        _parse_response(response, f"write secret at '{path}'")


def _is_kv2(mount_info: dict) -> bool:
    return mount_info.get("type") == "kv" and mount_info.get("options", {}).get("version") == "2"


def _parse_response(response: requests.Response, action: str) -> dict:
    if not response.ok:
        raise VaultError(
            f"Vault API request to {action} failed ({response.status_code}): {response.text[:500]}"
        )
    if not response.content:
        return {}
    return response.json()
