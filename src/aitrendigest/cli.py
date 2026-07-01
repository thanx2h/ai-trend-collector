from __future__ import annotations

from datetime import date

import typer

from aitrendigest.config import Settings
from aitrendigest.logging import configure_logging
from aitrendigest.pipeline import collect_enabled_sources, publish_new_items, run_once_for_scheduler

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


@app.command("run-once")
def run_once() -> None:
    """Process Telegram updates and send one scheduled digest batch."""
    configure_logging()
    settings = Settings.from_env()
    publisher = TelegramPublisher(None, settings.telegram_bot_token, settings.telegram_chat_id)
    message = run_once_for_scheduler(
        database_url=settings.database_url,
        telegram_client=publisher,
        publisher=publisher,
        today=date.today(),
        source_items=collect_enabled_sources(settings),
        default_period_days=settings.default_period_days,
    )
    typer.echo(message)


if __name__ == "__main__":
    app()
