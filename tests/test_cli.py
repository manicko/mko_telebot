"""Tests for the mko-telebot CLI commands.

Uses typer.testing.CliRunner to invoke CLI commands and verify output.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mko_telebot.cli import app
import pytest

runner: CliRunner = CliRunner()


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------


class TestCliHelp:
    """Tests for the --help option."""

    def test_help_shows_all_commands(self):
        """--help should display all five CLI commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("init", "validate", "run", "config", "version"):
            assert cmd in result.stdout


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


class TestCliVersion:
    """Tests for the version command."""

    def test_version_shows_version_string(self):
        """version should display a version string."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "version" in result.stdout.lower()
        # The installed version from pyproject.toml is 0.0.1
        assert "0.0.1" in result.stdout


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


class TestCliConfig:
    """Tests for the config command."""

    def test_config_shows_path_table(self):
        """config should display a table with application paths."""
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        # The table should reference file paths
        assert "Config file" in result.stdout
        assert "Secrets file" in result.stdout
        assert "Log directory" in result.stdout
        assert "User settings dir" in result.stdout


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestCliValidate:
    """Tests for the validate command."""

    def test_validate_exits_code_1_when_config_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
            """validate should exit code 1 when config files are missing."""
            from mko_telebot.core.paths import APP_PATHS

            monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)
            monkeypatch.setattr(APP_PATHS, "app_dir", tmp_path, raising=False)

            result = runner.invoke(app, ["validate"])
            assert result.exit_code == 1
            assert "Configuration error" in result.stdout


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


class TestCliInit:
    """Tests for the init command."""

    def test_init_creates_config_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
            """init should copy template files to the user config directory."""
            from mko_telebot.core.paths import APP_PATHS

            app_dir = Path(__file__).resolve().parent.parent / "src" / "mko_telebot"
            monkeypatch.setattr(APP_PATHS, "app_dir", app_dir, raising=False)
            monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0
            assert "Copied" in result.stdout

            # Check that files were actually copied
            settings_dir = tmp_path.joinpath("settings")
            assert settings_dir.exists()
            assert len(list(settings_dir.iterdir())) > 0

            # Verify the copied configuration can be loaded and validated
            from mko_telebot.core.config import TelepostConfigReader

            reader = TelepostConfigReader.from_user_dir()
            settings = reader.load()
            assert settings.channels.channels is not None

    def test_init_skips_existing_without_force(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
            """init without --force should skip existing files."""
            from mko_telebot.core.paths import APP_PATHS

            src_dir = Path(__file__).resolve().parent.parent / "src" / "mko_telebot"
            monkeypatch.setattr(APP_PATHS, "app_dir", src_dir, raising=False)
            monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

            # First init
            runner.invoke(app, ["init"])

            # Second init without force
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0
            assert "Skipped" in result.stdout

    def test_init_force_overwrites_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
            """init --force should overwrite existing files."""
            from mko_telebot.core.paths import APP_PATHS

            src_dir = Path(__file__).resolve().parent.parent / "src" / "mko_telebot"
            monkeypatch.setattr(APP_PATHS, "app_dir", src_dir, raising=False)
            monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

            # First init
            runner.invoke(app, ["init"])

            # Force init
            result = runner.invoke(app, ["init", "--force"])
            assert result.exit_code == 0
            assert "Copied" in result.stdout
            assert "Skipped" not in result.stdout

# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


class TestCliRun:
    """Tests for the run command error paths."""

    def test_run_missing_config_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """run should exit code 1 when config files are missing."""
        from mko_telebot.core.paths import APP_PATHS

        monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)
        monkeypatch.setattr(APP_PATHS, "app_dir", tmp_path, raising=False)

        result = runner.invoke(app, ["run"])
        assert result.exit_code == 1
        assert "Configuration error" in result.stdout

    def test_run_invalid_secrets_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """run should exit code 1 when secrets file has invalid content."""
        import yaml

        from mko_telebot.core.paths import APP_PATHS

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)

        # Write valid config.yaml
        config_data: dict[str, object] = {
            "CHANNELS": {
                "channels": {
                    "test_channel": {
                        "name": "@test_channel",
                    },
                },
            },
        }
        with (settings_dir / "config.yaml").open("w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Write secrets.yaml with missing required fields (no phone_or_token, no client)
        secrets_data: dict[str, object] = {
            "TELETHON_API": {
                "is_user": True,
            },
        }
        with (settings_dir / "secrets.yaml").open("w", encoding="utf-8") as f:
            yaml.dump(secrets_data, f)

        monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)
        monkeypatch.setattr(APP_PATHS, "app_dir", tmp_path, raising=False)

        result = runner.invoke(app, ["run"])
        assert result.exit_code == 1
        assert "Configuration error" in result.stdout
