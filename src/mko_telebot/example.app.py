"""
mko_telepost CLI application.

Commands:
    init     - Initialize user configuration
    run      - Run posting to Telegram
    config   - Show configuration paths
    version  - Show version info
"""

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mko_telepost.core import (
    APP_PATHS,
    APP_DIR,
    USER_DIR,
    TelepostConfigReader,
    TelepostSettings,
    init_project,
    run_posting,
)
import logging.config

logger = logging.getLogger(__name__)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    # Configure UTF-8 encoding for Windows emoji compatibility
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(
    name="mko-telepost",
    help="CLI tool for posting content from Google Sheets to Telegram",
    add_completion=True,
)

console = Console()


def _validate_and_categorize_errors(
    errors: list[str],
) -> tuple[list[str], list[str]]:
    """Categorize errors into warnings and critical errors.

    Args:
        errors: List of error messages from validation.

    Returns:
        Tuple of (warnings, critical_errors).
    """
    critical_keywords = ["credentials", "config"]
    critical_errors = [
        e for e in errors if any(k in e.lower() for k in critical_keywords)
    ]
    warnings = [e for e in errors if e not in critical_errors]
    return warnings, critical_errors


def _load_and_validate_config(
    config_path: Path | None,
) -> TelepostSettings | None:
    """Load config from file, validate, and return TelepostSettings or None."""
    custom_config_path = config_path
    if custom_config_path is not None:
        custom_config_path = custom_config_path.resolve()

    if config_path is None:
        config_path = APP_PATHS.app_config

    if not config_path.exists():
        console.print(f"[red]✒ Configuration not found:[/red] {config_path}")
        console.print()
        console.print(
            "   Run [cyan]mko-telepost init[/cyan] first to create configuration."
        )
        return None

    try:
        if custom_config_path is None:
            reader = TelepostConfigReader.from_user_dir()
        else:
            reader = TelepostConfigReader(config_path=custom_config_path)

        _inject_logging(reader)

        settings = reader.load()

        errors = reader.validate_files()
        if errors and _handle_config_errors(errors, console):
            return None

        console.print("[green]✓ Configuration loaded[/green]")
        console.print(f"   Chats configured: [cyan]{len(settings.chats.chats)}[/cyan]")

    except Exception:
        logger.exception("Configuration load failed")
        console.print("[red]✒ Configuration error. Check logs for details.[/red]")
        return None

    return settings


def _run_posting_flow(settings: TelepostSettings) -> None:
    """Execute the posting flow to Telegram.

    Args:
        settings: Validated Telepost configuration settings.
    """
    console.print()
    console.print("[bold]Starting posting...[/bold]")
    run_posting(settings=settings)


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration files",
    ),
):
    """
    Initialize user configuration.

    Creates user configuration directory with default template files.
    Run this command first before using other commands.

    Example:
        mko-telepost init
        mko-telepost init --force  # Overwrite existing files
    """
    console.print("[bold blue]Initializing mko_telepost...[/bold blue]")

    try:
        config_path = init_project(force=force)
        console.print("[green]✓ Configuration initialized[/green]")
        console.print(f"   Location: [cyan]{config_path}[/cyan]")
        console.print()
        console.print("   Next steps:")
        console.print("   1. Edit [cyan]app_config.yaml[/cyan] with your credentials")
        console.print(
            "   2. Download [cyan]credentials.json[/cyan] from Google Cloud Console"
        )
        console.print(
            "      (A template file with placeholders is included in the package)"
        )

    except Exception:
        logger.exception("Initialization failed")
        console.print("[red]✒ Initialization failed. Check logs for details.[/red]")
        raise typer.Exit(1) from None


# B008: typer.Option default is intentional pattern for CLI
@app.command()
def run(
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Path to custom configuration file",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate configuration without posting",
    ),
):
    """
    Run posting to Telegram.

    Reads configuration, fetches data from Google Sheets,
    and posts content to configured Telegram chats.

    Example:
        mko-telepost run
        mko-telepost run --config /path/to/config.yaml
        mko-telepost run --dry-run  # Validate without posting
    """
    console.print("[bold blue]Starting mko_telepost...[/bold blue]")

    settings = _load_and_validate_config(config_path)

    if settings is None:
        raise typer.Exit(1) from None

    if dry_run:
        console.print("[green]✓ Configuration is valid[/green]")
        _show_config_summary(settings)
        return

    try:
        _run_posting_flow(settings)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        raise typer.Exit(130) from None
    except Exception:
        logger.exception("Posting failed")
        console.print("[red]✒ Posting failed. Check logs for details.[/red]")
        raise typer.Exit(1) from None


@app.command()
def config() -> None:
    """
    Show configuration paths and status.

    Displays where configuration files are located and their status.
    """
    table = Table(title="mko_telepost Configuration Paths")
    table.add_column("Setting", style="cyan")
    table.add_column("Path", style="white", overflow="fold")
    table.add_column("Status", style="green")

    # Paths
    table.add_row("Package", str(APP_DIR), "✓")
    table.add_row("User Config", str(USER_DIR), "✓")

    # Config files
    user_config = APP_PATHS.user_settings_dir
    config_file = APP_PATHS.app_config
    log_file = APP_PATHS.log_config

    table.add_row(
        "User Settings Dir",
        str(user_config),
        "✓" if user_config.exists() else "✒ Not created",
    )
    table.add_row(
        "Config File",
        str(config_file),
        "✓" if config_file.exists() else "✒ Run mko-telepost init",
    )
    table.add_row(
        "Log Config",
        str(log_file),
        "✓" if log_file.exists() else "✒ Run mko-telepost init",
    )

    console.print(table)


@app.command()
def version() -> None:
    """Show version information."""
    try:
        from importlib.metadata import version

        ver = version("mko_telepost")
    except Exception:
        ver = "dev"

    console.print(f"[bold]mko_telepost[/bold] version [green]{ver}[/green]")


def _show_config_summary(settings: TelepostSettings) -> None:
    """Show summary of loaded configuration."""
    table = Table(title="Configuration Summary")
    table.add_column("Section", style="cyan")
    table.add_column("Value", style="white")

    # Google Sheets
    table.add_row("Spreadsheet ID", settings.google_sheets.spreadsheet_id)
    table.add_row("Filter Column", str(settings.google_sheets.filter_col))
    table.add_row("Filter Value", settings.google_sheets.filter_value)

    # Telethon
    telethon = settings.telethon
    auth_type = "User (phone)" if telethon.is_user else "Bot"
    table.add_row("Auth Type", auth_type)

    # Chats defaults
    defaults = settings.chats.defaults
    table.add_row(
        "Chat Defaults",
        f"delay={defaults.min_delay_minutes}min, jitter={defaults.delay_jitter_percent}%, max_photos={defaults.max_photos}",
    )
    table.add_row("  Max size", f"{defaults.max_width}x{defaults.max_height}")

    # Chats
    for i, chat in enumerate(settings.chats.chats, 1):
        table.add_row(f"Chat {i}", f"{chat.chat_name or chat.chat_id}")
        table.add_row(
            "  - Ranges",
            ", ".join(chat.range_names[:2])
            + ("..." if len(chat.range_names) > 2 else ""),
        )
        table.add_row("  - Min delay", f"{chat.min_delay_minutes} min")
        table.add_row("  - Max size", f"{chat.max_width}x{chat.max_height}")

    console.print(table)


# Main entry point
if __name__ == "__main__":
    app()

def _inject_logging(reader: TelepostConfigReader) -> None:
    """Configure logging from YAML config if available."""
    logging_config = reader.load_logging_config()
    if logging_config:
        logging.config.dictConfig(logging_config)

def _handle_config_errors(errors: list[str], console: Console) -> bool:
    """Handle file validation errors, printing warnings and critical errors.

    Args:
        errors: List of error messages from validation.
        console: Rich console for output.

    Returns:
        True if critical errors were found (caller should abort).
    """
    warnings, critical_errors = _validate_and_categorize_errors(errors)
    if critical_errors:
        for error in critical_errors:
            console.print(f"   • {error}")
        console.print(
            "[red]✒ Critical files missing. Run [cyan]mko-telepost init[/cyan] first.[/red]"
        )
        return True
    for error in warnings:
        console.print(f"   • {error}")
    return False
