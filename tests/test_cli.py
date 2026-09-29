from blipkit import __version__
from blipkit.cli import main


def test_version_is_pre_alpha() -> None:
    assert __version__.endswith(".dev0")


def test_cli_starts_with_help(capsys) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Blipkit game-audio toolkit" in output
    assert "create" in output
    assert "export" in output
