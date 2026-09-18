"""Integration-style test using real API responses captured from a local Vaultwarden.

Network calls are mocked, but the token/cipher payloads and the password below
are genuine values from a seeded local instance, so this exercises the real
authentication + decryption pipeline end to end.
"""

import json
from unittest.mock import patch

from bitwardensync.bitwarden import BitwardenClient

PASSWORD = "SeedMasterPassw0rd!123"

ACCESS_TOKEN = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9."
    "eyJuYmYiOjE3ODk3NDMyMTAsImV4cCI6MTc4OTc1MDQxMCwiaXNzIjoiaHR0cHM6Ly9sb2Nh"
    "bGhvc3Q6ODQ0M3xsb2dpbiIsInN1YiI6IjFiMWYxN2MzLTdkODUtNDE2ZC1iNGIyLWMzNmM2"
    "MDNlODFkMyIsInByZW1pdW0iOnRydWUsIm5hbWUiOiJEZW1vIFVzZXIiLCJlbWFpbCI6ImRl"
    "bW9AZXhhbXBsZS5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwic3N0YW1wIjoiNDc4ZDFk"
    "M2EtNDY2Yi00Y2U3LTljMTUtZjQ1ZmNhNGM3NjY3IiwiZGV2aWNlIjoiMDAwMDAwMDAtMDAw"
    "MC0wMDAwLTAwMDAtMDAwMDAwMDAwMDAwIiwiZGV2aWNldHlwZSI6IkxpbnV4IiwiY2xpZW50"
    "X2lkIjoidXNlci4xYjFmMTdjMy03ZDg1LTQxNmQtYjRiMi1jMzZjNjAzZTgxZDMiLCJzY29w"
    "ZSI6WyJhcGkiXSwiYW1yIjpbIkFwcGxpY2F0aW9uIl19."
    "dAGY3nn2WyYcDrv64oBXAxGh5e9VruV7uQBFQOSpUalfxZrV6rj6VBTUFDhS1m1NjBWtnCKn"
    "gW828SxwOzXEObfFKYDB9Ofsdzwkc1BxypPf9gqaFIoz0UR4vbRh0IFzlAT0_Zg2-Xb144oN"
    "s4EdrVBwQ9rBK5cGDn9ea2Fse_poe0Loh7JeYnqPCWygY-9RinpXTb1kno_151MaN3wTeYej"
    "skgkfPYA7slitjWybo0logrV_CZTv8NvCjNjzO9i709OxP1lWE6mbly3Eu1OZNq4T0GwVVDU"
    "3Ncg1sv99EZSt-lwWtAAxS9TkyHGN-TwArYB3i4yLZn22u7Zy4xmwQ"
)

TOKEN_RESPONSE = {
    "access_token": ACCESS_TOKEN,
    "Key": (
        "2.t/lLLJdiZ3LpXlWfRMqrIw==|nmb5681Ti/xRtj9yubEAhRd4O5urUVBWVUxyF67+"
        "5joACAQPmJVhDH0qpzMyDa+8T/2nLL5pplERIed68ORH7TJcumByWIc9CovBYllliYA="
        "|PjQ4viR1q1PeHzhcHaMGdB07qrZ6nyDjW/cinYffQHQ="
    ),
    "Kdf": 0,
    "KdfIterations": 600000,
    "KdfMemory": None,
    "KdfParallelism": None,
    "token_type": "Bearer",
}

SYNC_RESPONSE = {
    "ciphers": [
        {
            "id": "44ae0ae5-d70c-4e7a-b79c-6c1f48745f52",
            "organizationId": None,
            "key": None,
            "name": (
                "2.C7bPwRrf4UAvm8ekp8Sxng==|G+87tjmsI07CReaFq/zlqN6hc186vKivzoHPh"
                "Fyjl5s=|AV5crNEeEuiBkyGqe/6vGgmNZMtw/nAwI9iQYvP6MvQ="
            ),
            "notes": None,
            "fields": [],
            "login": {
                "username": (
                    "2.E89NsHBNaUdAFfSpiiDjNg==|LAqaJZH0JqDvSgofpzamjw==|pA1cPjlp"
                    "TFBU+Po9UJXBMuQJUk6jvq8S/zDllU+4smU="
                ),
                "password": (
                    "2.IDH6i4rJcT3aLy4v8nCgfw==|ni3rmsqxWGy/SFIRF6Ef8Y5kNqmPRJJw"
                    "AbgC947J4yo=|vkS6Hsk50kG/ZVunl9F/VLqDibxnvGnRozs5QXPVkiY="
                ),
                "uris": [],
            },
        },
        {
            # Organization-owned item: should be skipped, since we don't
            # implement org-key unwrapping.
            "id": "org-owned-item",
            "organizationId": "some-org-id",
            "key": None,
            "name": "2.does-not-matter==|xx==|xx=",
            "notes": None,
            "fields": [],
            "login": {"username": None, "password": None, "uris": []},
        },
    ]
}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.ok = True
        self.status_code = 200
        self.text = json.dumps(payload)
        self.url = "https://example.test"

    def json(self):
        return self._payload


def test_list_items_authenticates_and_decrypts_real_data():
    def fake_post(url, data=None, **kwargs):
        assert url.endswith("/identity/connect/token")
        assert data["grant_type"] == "client_credentials"
        assert data["client_id"] == "user.abc"
        assert data["client_secret"] == "secret"
        return _FakeResponse(TOKEN_RESPONSE)

    def fake_get(url, headers=None, **kwargs):
        assert url.endswith("/api/sync")
        assert headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
        return _FakeResponse(SYNC_RESPONSE)

    with patch("requests.Session.post", side_effect=fake_post):
        with patch("requests.Session.get", side_effect=fake_get):
            client = BitwardenClient(
                client_id="user.abc",
                client_secret="secret",
                password=PASSWORD,
                server_url="https://localhost:8443",
            )
            items = client.list_items()

    assert len(items) == 1
    assert items[0].name == "Postgres (staging)"
    assert items[0].fields == {
        "username": "app_user",
        "password": "staging-db-pass-789",
    }
