"""Smoke tests for the bootstrap skeleton (E0). Keep tiny and offline."""

import dataset_compiler
from dataset_compiler.cli import main


def test_version_present() -> None:
    assert dataset_compiler.__version__


def test_cli_no_command_prints_help_and_exits_zero() -> None:
    assert main([]) == 0


def test_cli_planned_command_exits_two() -> None:
    assert main(["plan"]) == 2
    assert main(["spec", "lint"]) == 2
