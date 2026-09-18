import json
from unittest.mock import patch

from bitwardensync.vault import VaultClient, VaultError, VaultPermissionError


class _FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = text or (json.dumps(payload) if payload is not None else "")
        self.content = self.text.encode()

    def json(self):
        return self._payload


def _client(token="root", mount="secret"):
    return VaultClient(addr="http://localhost:8200", token=token, mount=mount)


def test_kv2_mount_exists_true():
    mounts = {"secret/": {"type": "kv", "options": {"version": "2"}}}
    with patch("requests.Session.get", return_value=_FakeResponse(mounts)):
        assert _client().kv2_mount_exists() is True


def test_kv2_mount_exists_false_when_missing():
    with patch("requests.Session.get", return_value=_FakeResponse({})):
        assert _client().kv2_mount_exists() is False


def test_kv2_mount_exists_false_for_kv_v1():
    mounts = {"secret/": {"type": "kv", "options": {"version": "1"}}}
    with patch("requests.Session.get", return_value=_FakeResponse(mounts)):
        assert _client().kv2_mount_exists() is False


def test_ensure_kv2_mount_noop_when_already_present():
    mounts = {"secret/": {"type": "kv", "options": {"version": "2"}}}
    with patch("requests.Session.get", return_value=_FakeResponse(mounts)):
        with patch("requests.Session.post") as post:
            _client().ensure_kv2_mount()
            post.assert_not_called()


def test_ensure_kv2_mount_creates_when_missing():
    with patch("requests.Session.get", return_value=_FakeResponse({})):
        with patch("requests.Session.post", return_value=_FakeResponse({}, 204)) as post:
            _client(mount="new-mount").ensure_kv2_mount()
            post.assert_called_once()
            args, kwargs = post.call_args
            assert args[0].endswith("/v1/sys/mounts/new-mount")
            assert kwargs["json"] == {"type": "kv", "options": {"version": "2"}}


def test_ensure_kv2_mount_raises_permission_error_on_create_403():
    with patch("requests.Session.get", return_value=_FakeResponse({})):
        with patch("requests.Session.post", return_value=_FakeResponse(status_code=403)):
            try:
                _client(mount="new-mount").ensure_kv2_mount()
                raise AssertionError("expected VaultPermissionError")
            except VaultPermissionError:
                pass


def test_get_mount_info_raises_permission_error_on_list_403():
    with patch("requests.Session.get", return_value=_FakeResponse(status_code=403)):
        try:
            _client().kv2_mount_exists()
            raise AssertionError("expected VaultPermissionError")
        except VaultPermissionError:
            pass


def test_ensure_kv2_mount_raises_on_wrong_engine_type():
    mounts = {"secret/": {"type": "system", "options": None}}
    with patch("requests.Session.get", return_value=_FakeResponse(mounts)):
        try:
            _client().ensure_kv2_mount()
            raise AssertionError("expected VaultError")
        except VaultPermissionError:
            raise AssertionError("should not be a permission error")
        except VaultError:
            pass


def test_write_secret_posts_data():
    with patch("requests.Session.post", return_value=_FakeResponse({"data": {}})) as post:
        _client().write_secret("foo/bar", {"username": "u", "password": "p"})
        args, kwargs = post.call_args
        assert args[0] == "http://localhost:8200/v1/secret/data/foo/bar"
        assert kwargs["json"] == {"data": {"username": "u", "password": "p"}}
