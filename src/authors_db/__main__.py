"""Command line interface: `python -m authors_db run`."""

import typer

from authors_db import pipeline

app = typer.Typer(add_completion=False, help="Build the authors database.")


@app.callback()
def main() -> None:
    """Build the authors database."""


@app.command()
def run(
    limit: int | None = typer.Option(None, help="Process only the first N seed names."),
    offline: bool = typer.Option(False, help="Read only from the cache. Make no request."),
    adjudicate: bool = typer.Option(False, help="Use the local model for ambiguous rows."),
) -> None:
    """Run the full pipeline."""
    run_id = pipeline.run(limit=limit, offline=offline, adjudicate=adjudicate)
    typer.echo(f"Run {run_id} finished.")


if __name__ == "__main__":
    app()
