"""Tests for CLI - basic invocation tests."""

from typer.testing import CliRunner

runner = CliRunner()


class TestCLICommands:
    """Tests for CLI commands - basic invocation."""

    def test_clone_command_help(self):
        """clone command should show help."""
        from tts_lab.cli import app

        result = runner.invoke(app, ["clone", "--help"])
        assert result.exit_code == 0

    def test_generate_command_help(self):
        """generate command should show help."""
        from tts_lab.cli import app

        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0

    def test_app_help(self):
        """app should show help with all commands."""
        from tts_lab.cli import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "clone" in result.stdout
        assert "generate" in result.stdout
