"""CLI entrypoint.

The full command surface is declared up front (docs/architecture.md §4). Implementations land per
the epic tree: spec lint/plan in E1, catalog in E2, evaluate in E3, build/verify/explain/
materialize in E5. At bootstrap every command exits 2 (planned, not implemented) without side
effects.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__

PLANNED = ("plan", "catalog", "evaluate", "build", "verify", "explain", "materialize")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataset-compiler",
        description=(
            "Declarative purpose-specific dataset compilation "
            "(DatasetSpec -> BuildManifest)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    spec = sub.add_parser("spec", help="specification tooling")
    spec_sub = spec.add_subparsers(dest="spec_command", metavar="SUBCOMMAND")
    spec_sub.add_parser("lint", help="validate a DatasetSpec with stable diagnostics (E1)")

    for name in PLANNED:
        sub.add_parser(name, help="(planned) see PLAN.md for the owning epic")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "command", None) is None:
        parser.print_help()
        return 0
    print(
        f"dataset-compiler: '{args.command}' is planned but not implemented in the bootstrap "
        "skeleton; see PLAN.md for the owning epic (E1-E6).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
