import tomllib
from pathlib import Path

from blipkit import __version__
from blipkit.cli import main


def test_version() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert __version__ == metadata["project"]["version"]


def test_cli_starts_with_help(capsys) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Blipkit game-audio toolkit" in output
    assert "create" in output
    assert "export" in output
