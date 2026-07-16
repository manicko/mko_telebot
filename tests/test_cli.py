"""Tests for the mko-telebot CLI commands.

Uses typer.testing.CliRunner to invoke CLI commands and verify output.
"""

from __future__ import annotations

from pathlib import Path

import yaml

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
        assert "Telethon config file" in result.stdout
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

        # Verify the copied telethon_config.yaml has placeholder sentinel values
        # (intentionally fails validation - users must customize it)
        telethon_data = yaml.safe_load(
            (settings_dir / "telethon_config.yaml").read_text(encoding="utf-8")
        )
        assert telethon_data["TELETHON_API"]["client"]["api_id"] == 12345
        assert "PLACEHOLDER_REPLACE_ME" in telethon_data["TELETHON_API"]["phone_or_token"]

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
            """init --force should overwrite existing files except telethon_config.yaml."""
            from mko_telebot.core.paths import APP_PATHS

            src_dir = Path(__file__).resolve().parent.parent / "src" / "mko_telebot"
            monkeypatch.setattr(APP_PATHS, "app_dir", src_dir, raising=False)
            monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

            # First init
            runner.invoke(app, ["init"])

            # Modify telethon_config.yaml to simulate user credentials
            settings_dir = tmp_path / "settings"
            user_config = settings_dir / "telethon_config.yaml"
            user_config.write_text("TELETHON_API:\n  is_user: true\n  phone_or_token: 'user_phone'\n  client:\n    api_id: 99999\n    api_hash: 'user_api_hash'\n", encoding="utf-8")

            # Force init
            result = runner.invoke(app, ["init", "--force"])
            assert result.exit_code == 0
            assert "Copied" in result.stdout
            assert "Preserved existing telethon_config.yaml" in result.stdout

            # Verify telethon_config.yaml was preserved (not overwritten)
            telethon_data = yaml.safe_load(user_config.read_text(encoding="utf-8"))
            assert telethon_data["TELETHON_API"]["client"]["api_id"] == 99999
            assert telethon_data["TELETHON_API"]["phone_or_token"] == "user_phone"

    def test_init_force_copies_telethon_config_when_not_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """init --force should copy telethon_config.yaml if user file does not exist."""
        from mko_telebot.core.paths import APP_PATHS

        src_dir = Path(__file__).resolve().parent.parent / "src" / "mko_telebot"
        monkeypatch.setattr(APP_PATHS, "app_dir", src_dir, raising=False)
        monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)

        # First init
        runner.invoke(app, ["init"])

        # Remove telethon_config.yaml
        settings_dir = tmp_path / "settings"
        user_config = settings_dir / "telethon_config.yaml"
        user_config.unlink()

        # Force init
        result = runner.invoke(app, ["init", "--force"])
        assert result.exit_code == 0
        assert "Copied" in result.stdout
        assert "Preserved" not in result.stdout

        # Verify telethon_config.yaml was copied
        assert user_config.exists()
        telethon_data = yaml.safe_load(user_config.read_text(encoding="utf-8"))
        assert telethon_data["TELETHON_API"]["client"]["api_id"] == 12345


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

    def test_run_invalid_telethon_config_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """run should exit code 1 when telethon config file has invalid content."""
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

        # Write telethon_config.yaml with missing required fields (no phone_or_token, no client)
        telethon_config_data: dict[str, object] = {
            "TELETHON_API": {
                "is_user": True,
            },
        }
        with (settings_dir / "telethon_config.yaml").open("w", encoding="utf-8") as f:
            yaml.dump(telethon_config_data, f)

        monkeypatch.setattr(APP_PATHS, "user_dir", tmp_path, raising=False)
        monkeypatch.setattr(APP_PATHS, "app_dir", tmp_path, raising=False)

        result = runner.invoke(app, ["run"])
        assert result.exit_code == 1
        assert "Configuration error" in result.stdout
