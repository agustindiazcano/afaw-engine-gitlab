"""Entry point for uvicorn: ``uvicorn afaw_web.main:app``."""

from afaw_web.app import create_app

app = create_app()
