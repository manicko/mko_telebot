"""CLI entry point for mko_telebot.

Provides a Typer application with five commands:
init, validate, run, config, version.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from importlib.metadata import version as pkg_version
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mko_telebot.core.errors import ConfigError, MkoTelebotError
from mko_telebot.core.paths import APP_PATHS
from mko_telebot.monitor import create_client, run_monitor
from mko_telebot.logging import setup_logging
from mko_telebot.core.config import TelepostConfigReader

logger = logging.getLogger(__name__)

app: typer.Typer = typer.Typer(
    name="mko-telebot",
    help="Scans Telegram channels for new messages matching your keywords and forwards them automatically.",
)
console: Console = Console()


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing user config files if they exist.",
    ),
) -> None:
    """Copy default template files to the user config directory."""
    src: Path = APP_PATHS.app_settings_dir
    dst: Path = APP_PATHS.user_settings_dir

    if not src.exists():
        console.print("[red]ERROR:[/red] Template settings directory not found.")
        raise typer.Exit(code=1)

    dst.mkdir(parents=True, exist_ok=True)

    copied: int = 0
    skipped: int = 0

    for item in src.iterdir():
        if not item.is_file():
            continue
        target: Path = dst / item.name
        if target.exists() and not force:
            skipped += 1
            continue
        shutil.copy2(item, target)
        copied += 1

    console.print(f"[green]Copied {copied} file(s) to {dst}.[/green]")
    if skipped:
        console.print(
            f"[yellow]Skipped {skipped} existing file(s). Use --force to overwrite.[/yellow]"
        )


@app.command()
def validate() -> None:
    """Validate configuration files without running the monitor."""
    try:
        reader: TelepostConfigReader = TelepostConfigReader.from_user_dir()
        reader.validate_files()
        console.print("[green]Configuration files are valid.[/green]")
    except ConfigError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def run() -> None:
    """Start the Telegram monitoring service."""
    setup_logging()
    try:
        reader: TelepostConfigReader = TelepostConfigReader.from_user_dir()
        settings = reader.load()
    except MkoTelebotError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(code=1) from e

    client = create_client(settings)
    try:
        asyncio.run(run_monitor(settings, client))
    except (MkoTelebotError, KeyboardInterrupt):
        console.print("[red]Error:[/red] Failed to run monitor")
        raise typer.Exit(code=1) from None


@app.command()
def config() -> None:
    """Display all application path locations."""
    table: Table = Table(title="Application Paths")
    table.add_column("Path", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Config file", str(APP_PATHS.config_file))
    table.add_row("Secrets file", str(APP_PATHS.secrets_file))
    table.add_row("Log config file", str(APP_PATHS.log_config_file))
    table.add_row("State directory", str(APP_PATHS.state_dir))
    table.add_row("Session directory", str(APP_PATHS.session_dir))
    table.add_row("Log directory", str(APP_PATHS.log_dir))
    table.add_row("App settings dir", str(APP_PATHS.app_settings_dir))
    table.add_row("User settings dir", str(APP_PATHS.user_settings_dir))

    console.print(table)


@app.command()
def version() -> None:
    """Show the installed version of mko-telebot."""
    ver: str = pkg_version("mko-telebot")
    console.print(f"mko-telebot version [bold]{ver}[/bold]")


if __name__ == "__main__":
    app()