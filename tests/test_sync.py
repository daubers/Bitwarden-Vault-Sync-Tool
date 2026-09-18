from unittest.mock import MagicMock, patch

from bitwardensync.bitwarden import BitwardenItem
from bitwardensync.config import Config
from bitwardensync.sync import run_sync

CONFIG = Config(
    bw_client_id="cid",
    bw_client_secret="csecret",
    bw_password="pw",
    vault_addr="http://localhost:8200",
    vault_token="root",
    vault_path_prefix="bitwarden",
)

ITEM = BitwardenItem(id="1", name="Example", fields={"username": "u", "password": "p"})


def _run(existing, on_conflict="bitwarden", dry_run=False):
    fake_bitwarden = MagicMock()
    fake_bitwarden.list_items.return_value = [ITEM]

    fake_vault = MagicMock()
    fake_vault.read_secret.return_value = existing

    with patch("bitwardensync.sync.BitwardenClient", return_value=fake_bitwarden):
        with patch("bitwardensync.sync.VaultClient", return_value=fake_vault):
            run_sync(CONFIG, on_conflict=on_conflict, dry_run=dry_run)

    return fake_vault


def test_creates_when_not_in_vault():
    vault = _run(existing=None)
    vault.write_secret.assert_called_once_with("bitwarden/Example", ITEM.fields)


def test_skips_when_already_in_sync():
    vault = _run(existing=dict(ITEM.fields))
    vault.write_secret.assert_not_called()


def test_bitwarden_wins_conflict_by_default():
    vault = _run(existing={"username": "u", "password": "stale"})
    vault.write_secret.assert_called_once_with("bitwarden/Example", ITEM.fields)


def test_vault_wins_conflict_when_flag_set():
    vault = _run(existing={"username": "u", "password": "stale"}, on_conflict="vault")
    vault.write_secret.assert_not_called()


def test_dry_run_never_writes():
    vault = _run(existing=None, dry_run=True)
    vault.write_secret.assert_not_called()

    vault = _run(existing={"username": "u", "password": "stale"}, dry_run=True)
    vault.write_secret.assert_not_called()
