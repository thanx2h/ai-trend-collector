from __future__ import annotations

import typer

from aitrendigest.config import Settings
from aitrendigest.logging import configure_logging
from aitrendigest.pipeline import collect_enabled_sources, publish_new_items

app = typer.Typer(add_completion=False)


@app.command()
def collect() -> None:
    """Fetch items from enabled sources and report the count."""
    configure_logging()
    settings = Settings.from_env()
    items = collect_enabled_sources(settings)
    typer.echo(f"Collected {len(items)} items")


@app.command()
def publish(dry_run: bool = typer.Option(False, "--dry-run", help="Render the digest without sending it.")) -> None:
    """Build the daily digest from live sources and send it to Telegram."""
    configure_logging()
    settings = Settings.from_env()
    message = publish_new_items(settings, dry_run=dry_run)
    typer.echo(message)


if __name__ == "__main__":
    app()
