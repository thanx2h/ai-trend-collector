from __future__ import annotations

import typer

from aitrendigest.config import Settings
from aitrendigest.db import create_schema, create_session_factory
from aitrendigest.logging import configure_logging
from aitrendigest.pipeline import collect_enabled_sources, publish_new_items
from aitrendigest.repository import ItemRepository

app = typer.Typer(add_completion=False)


@app.command()
def collect() -> None:
    """Fetch items from enabled sources and store them."""
    configure_logging()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    create_schema(session_factory)
    repository = ItemRepository(session_factory)
    collected_count = collect_enabled_sources(settings, repository)
    typer.echo(f"Collected {collected_count} items")


@app.command()
def publish(dry_run: bool = typer.Option(False, "--dry-run", help="Render the digest without sending it.")) -> None:
    """Build the daily digest from stored items and send it to Telegram."""
    configure_logging()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    create_schema(session_factory)
    repository = ItemRepository(session_factory)
    message = publish_new_items(settings, repository, dry_run=dry_run)
    typer.echo(message)


if __name__ == "__main__":
    app()
