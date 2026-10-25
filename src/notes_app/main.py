"""Entry point for uvicorn: ``uvicorn notes_app.main:app``."""

from notes_app.app import create_app

app = create_app()
