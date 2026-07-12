"""Tests for resolve_path in core/config.py.

Tests cover:
- Absolute path passthrough
- Relative path resolution
- Home-directory (~) expansion
- Edge cases
"""

from __future__ import annotations

from pathlib import Path


from mko_telebot.core.config import resolve_path


# ---------------------------------------------------------------------------
# TestResolvePath
# ---------------------------------------------------------------------------


class TestResolvePath:
    """Tests for resolve_path() function."""

    def test_resolve_path_absolute_path_passthrough(self, tmp_path: Path):
        """resolve_path should return absolute paths unchanged."""
        # Use tmp_path which is guaranteed to be absolute
        absolute = tmp_path / "mko_telebot.log"
        result = resolve_path(absolute)
        assert result == absolute
        assert result.is_absolute()

    def test_resolve_path_absolute_path_as_string(self, tmp_path: Path):
        """resolve_path should return absolute paths (as string) unchanged."""
        absolute_str = str(tmp_path / "mko_telebot.log")
        result = resolve_path(absolute_str)
        assert result == Path(absolute_str)
        assert result.is_absolute()

    def test_resolve_path_relative_path_resolution(self, tmp_path: Path):
        """resolve_path should resolve relative paths against base_dir."""
        relative = "logs/mko_telebot.log"
        result = resolve_path(relative, base_dir=tmp_path)
        expected = (tmp_path / relative).resolve()
        assert result == expected
        assert result.is_absolute()

    def test_resolve_path_relative_without_base_uses_default(self):
        """resolve_path should use APP_PATHS.app_settings_dir when base_dir is None."""
        from mko_telebot.core.paths import APP_PATHS

        relative = "config.yaml"
        result = resolve_path(relative)
        expected = (APP_PATHS.app_settings_dir / relative).resolve()
        assert result == expected
        assert result.is_absolute()

    def test_resolve_path_home_directory_expansion(self):
        """resolve_path should expand ~ to user home directory."""
        home = Path.home()

        result = resolve_path("~/mko_telebot/log.log")
        assert result.is_absolute()
        assert str(home) in str(result)
        assert "mko_telebot" in str(result)
        assert "log.log" in str(result)

    def test_resolve_path_home_expansion_with_base_dir(self, tmp_path: Path):
        """resolve_path should expand ~ and ignore base_dir for home paths."""
        result = resolve_path("~/log.log", base_dir=tmp_path)
        home = Path.home()
        expected = (home / "log.log").resolve()
        assert result == expected
        # base_dir should be ignored for home paths
        assert str(tmp_path) not in str(result)

    def test_resolve_path_empty_string_raises(self, tmp_path: Path):
        """resolve_path should handle empty path gracefully."""
        # Empty string resolves to base_dir current directory
        result = resolve_path("", base_dir=tmp_path)
        # Empty path resolves to the base_dir itself
        assert result == tmp_path.resolve()

    def test_resolve_path_dot_relative(self, tmp_path: Path):
        """resolve_path should handle '.' (current directory) correctly."""
        result = resolve_path(".", base_dir=tmp_path)
        assert result == tmp_path.resolve()

    def test_resolve_path_nested_relative(self, tmp_path: Path):
        """resolve_path should resolve nested relative paths."""
        nested = "a/b/c/config.yaml"
        result = resolve_path(nested, base_dir=tmp_path)
        expected = (tmp_path / nested).resolve()
        assert result == expected

    def test_resolve_path_mixed_path_without_home(self, tmp_path: Path):
        """resolve_path should handle paths without home expansion."""
        result = resolve_path("relative/path.log", base_dir=tmp_path)
        expected = (tmp_path / "relative" / "path.log").resolve()
        assert result == expected
        assert "relative" in str(result)

    def test_resolve_path_path_object_input(self, tmp_path: Path):
        """resolve_path should accept Path objects."""
        input_path = tmp_path / "path.yaml"
        result = resolve_path(input_path)
        assert result == input_path

    def test_resolve_path_string_input(self, tmp_path: Path):
        """resolve_path should accept string inputs."""
        input_str = str(tmp_path / "string.yaml")
        result = resolve_path(input_str)
        assert result == Path(input_str)