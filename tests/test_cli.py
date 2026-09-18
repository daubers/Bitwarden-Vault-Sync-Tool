from bitwardensync.cli import build_parser


def test_dry_run_flag_parses():
    parser = build_parser()
    args = parser.parse_args(["--dry-run"])
    assert args.dry_run is True
