from __future__ import annotations

import argparse
import sys

from bitwardensync.config import Config
from bitwardensync.sync import run_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bitwardensync",
        description="Sync secrets from Bitwarden into a HashiCorp Vault KV store",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be synced without writing to Vault",
    )
    parser.add_argument(
        "--on-conflict",
        choices=["bitwarden", "vault"],
        default="bitwarden",
        help=(
            "When a secret exists in both with different values, which one "
            "wins: 'bitwarden' overwrites Vault (default), 'vault' leaves "
            "Vault untouched"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = Config.from_env()
    run_sync(config, on_conflict=args.on_conflict, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
