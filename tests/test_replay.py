from click.testing import CliRunner

from main import main as cli
from tests.test_cli import SID, seeded_db  # noqa: F401 -- seeded_db is a fixture


def test_replay_dry_run(seeded_db):
    """replay --session <id> --dry-run fires zero requests"""
    result = CliRunner().invoke(
        cli, ["replay", "--db", seeded_db, "--session", SID, "--dry-run"]
    )
    assert result.exit_code == 0
    assert "Dry run" in result.output
    assert "Firing request" not in result.output


def test_replay_confirm(seeded_db):
    """replay --confirm prompts on mutating calls; 'y' fires them"""
    result = CliRunner().invoke(
        cli, ["replay", "--db", seeded_db, "--session", SID, "--confirm"],
        input="y\n",
    )
    assert result.exit_code == 0
    assert "Firing request: search" in result.output
    assert "Firing request: send_email" in result.output


def test_replay_confirm_skip(seeded_db):
    """replay --confirm with 'n' skips the mutating call"""
    result = CliRunner().invoke(
        cli, ["replay", "--db", seeded_db, "--session", SID, "--confirm"],
        input="n\n",
    )
    assert result.exit_code == 0
    assert "Skipping send_email" in result.output
    assert "Firing request: send_email" not in result.output
