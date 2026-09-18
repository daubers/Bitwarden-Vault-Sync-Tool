from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import requests

from bitwardensync import crypto

DEFAULT_SERVER_URL = "https://vault.bitwarden.com"

# Bitwarden's identity endpoint wants a device identity; these don't need to
# be unique or persistent for an API-key (service) login, so they're fixed.
DEVICE_TYPE = "8"  # "Linux" device type; arbitrary but must be a known enum value
DEVICE_IDENTIFIER = "bitwardensync"
DEVICE_NAME = "bitwardensync"


class BitwardenError(RuntimeError):
    """Raised when the Bitwarden API returns an error or unexpected data."""


@dataclass
class BitwardenItem:
    id: str
    name: str
    fields: dict[str, str]


class BitwardenClient:
    """Lists Bitwarden vault items by talking to the Bitwarden API directly.

    Authenticates with a personal API key (OAuth2 client_credentials grant),
    then decrypts the vault client-side using the master password, exactly
    like the official clients do — the server never sees the plaintext
    password. No external `bw` CLI required.

    Only personal (non-organization) items are decrypted; organization-owned
    items are skipped, since unwrapping an org key requires the account's
    RSA keypair, which isn't implemented here.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        password: str,
        server_url: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._password = password
        self._base_url = (server_url or DEFAULT_SERVER_URL).rstrip("/")
        self._session = requests.Session()

    def list_items(self) -> list[BitwardenItem]:
        token_response = self._authenticate()
        access_token = token_response["access_token"]
        email = _email_from_access_token(access_token)

        kdf = crypto.KdfConfig(
            kdf_type=token_response["Kdf"],
            iterations=token_response["KdfIterations"],
            memory_mb=token_response.get("KdfMemory"),
            parallelism=token_response.get("KdfParallelism"),
        )
        master_key = crypto.derive_master_key(self._password, email, kdf)
        stretched = crypto.stretch_key(master_key)
        user_key = crypto.decrypt(token_response["Key"], stretched[:32], stretched[32:])
        user_enc_key, user_mac_key = user_key[:32], user_key[32:]

        sync_data = self._sync(access_token)

        items = []
        for cipher in sync_data.get("ciphers", []):
            if cipher.get("organizationId") is not None:
                continue
            items.append(_decrypt_cipher(cipher, user_enc_key, user_mac_key))
        return items

    def _authenticate(self) -> dict:
        response = self._session.post(
            f"{self._base_url}/identity/connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "api",
                "deviceType": DEVICE_TYPE,
                "deviceIdentifier": DEVICE_IDENTIFIER,
                "deviceName": DEVICE_NAME,
            },
        )
        return _parse_response(response)

    def _sync(self, access_token: str) -> dict:
        response = self._session.get(
            f"{self._base_url}/api/sync",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return _parse_response(response)


def _parse_response(response: requests.Response) -> dict:
    if not response.ok:
        raise BitwardenError(
            f"Bitwarden API request to {response.url} failed "
            f"({response.status_code}): {response.text[:500]}"
        )
    return response.json()


def _email_from_access_token(access_token: str) -> str:
    payload_b64 = access_token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    email = payload.get("email")
    if not email:
        raise BitwardenError("Access token did not contain an email claim")
    return email


def _decrypt_cipher(cipher: dict, user_enc_key: bytes, user_mac_key: bytes) -> BitwardenItem:
    enc_key, mac_key = user_enc_key, user_mac_key

    cipher_key = cipher.get("key")
    if cipher_key is not None:
        item_key = crypto.decrypt(cipher_key, user_enc_key, user_mac_key)
        enc_key, mac_key = item_key[:32], item_key[32:]

    fields: dict[str, str] = {}

    login = cipher.get("login") or {}
    username = crypto.decrypt_str(login.get("username"), enc_key, mac_key)
    if username is not None:
        fields["username"] = username
    password = crypto.decrypt_str(login.get("password"), enc_key, mac_key)
    if password is not None:
        fields["password"] = password
    uris = login.get("uris") or []
    if uris:
        uri = crypto.decrypt_str(uris[0].get("uri"), enc_key, mac_key)
        if uri is not None:
            fields["uri"] = uri

    notes = crypto.decrypt_str(cipher.get("notes"), enc_key, mac_key)
    if notes:
        fields["notes"] = notes

    for custom_field in cipher.get("fields") or []:
        name = crypto.decrypt_str(custom_field.get("name"), enc_key, mac_key)
        value = crypto.decrypt_str(custom_field.get("value"), enc_key, mac_key)
        if name:
            fields[name] = value or ""

    name = crypto.decrypt_str(cipher["name"], enc_key, mac_key) or ""
    return BitwardenItem(id=cipher["id"], name=name, fields=fields)
