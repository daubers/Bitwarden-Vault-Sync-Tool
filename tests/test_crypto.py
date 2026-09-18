"""Regression tests using real values captured from a local Vaultwarden instance."""

from bitwardensync import crypto

EMAIL = "demo@example.com"
PASSWORD = "SeedMasterPassw0rd!123"
KDF = crypto.KdfConfig(kdf_type=0, iterations=600000)

# The account's protected symmetric key, as returned by /identity/connect/token.
PROTECTED_KEY = (
    "2.t/lLLJdiZ3LpXlWfRMqrIw==|nmb5681Ti/xRtj9yubEAhRd4O5urUVBWVUxyF67+5jo"
    "ACAQPmJVhDH0qpzMyDa+8T/2nLL5pplERIed68ORH7TJcumByWIc9CovBYllliYA=|PjQ4"
    "viR1q1PeHzhcHaMGdB07qrZ6nyDjW/cinYffQHQ="
)

NAME_ENC = (
    "2.C7bPwRrf4UAvm8ekp8Sxng==|G+87tjmsI07CReaFq/zlqN6hc186vKivzoHPhFyjl5"
    "s=|AV5crNEeEuiBkyGqe/6vGgmNZMtw/nAwI9iQYvP6MvQ="
)
PASSWORD_ENC = (
    "2.IDH6i4rJcT3aLy4v8nCgfw==|ni3rmsqxWGy/SFIRF6Ef8Y5kNqmPRJJwAbgC947J4y"
    "o=|vkS6Hsk50kG/ZVunl9F/VLqDibxnvGnRozs5QXPVkiY="
)


def test_derive_master_key_and_decrypt_user_key():
    master_key = crypto.derive_master_key(PASSWORD, EMAIL, KDF)
    stretched = crypto.stretch_key(master_key)
    user_key = crypto.decrypt(PROTECTED_KEY, stretched[:32], stretched[32:])

    assert len(user_key) == 64


def test_decrypt_cipher_fields_matches_seeded_values():
    master_key = crypto.derive_master_key(PASSWORD, EMAIL, KDF)
    stretched = crypto.stretch_key(master_key)
    user_key = crypto.decrypt(PROTECTED_KEY, stretched[:32], stretched[32:])
    enc_key, mac_key = user_key[:32], user_key[32:]

    assert crypto.decrypt_str(NAME_ENC, enc_key, mac_key) == "Postgres (staging)"
    assert crypto.decrypt_str(PASSWORD_ENC, enc_key, mac_key) == "staging-db-pass-789"
