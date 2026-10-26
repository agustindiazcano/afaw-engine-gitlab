"""AFAW demo notes: a tiny app that the Duo flows change through issues.

It exists so the hands-off loop has something visible to act on: an issue asks for a feature or a
fix here, the pipeline judges the merge request, and the live service shows the result. Notes are
kept in memory per instance (the service scales to zero), which is stated on the page.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints

MAX_TEXT = 200
MAX_NOTES = 100

STATIC_PAGE = Path(__file__).parent / "static" / "index.html"


class NoteIn(BaseModel):
    """A note to add: trimmed text of 1 to MAX_TEXT characters, no other field."""

    model_config = ConfigDict(extra="forbid")
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)
    ]


class NotePatch(BaseModel):
    """A change to a note: the done flag, a real boolean, no other field."""

    model_config = ConfigDict(extra="forbid")
    done: StrictBool


Note = dict[str, int | str | bool]


def _env(name: str) -> str:
    """Return an environment variable, or "unknown" when it is unset or empty."""
    return os.environ.get(name) or "unknown"


def create_app() -> FastAPI:
    """Build the app with its own empty in-memory store."""
    app = FastAPI(title="AFAW demo notes")
    notes: list[Note] = []
    next_id = 1
    lock = threading.Lock()
    page_html = STATIC_PAGE.read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return page_html

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/version")
    def version() -> dict[str, str]:
        return {"release_tag": _env("AFAW_RELEASE_TAG"), "commit_sha": _env("AFAW_COMMIT_SHA")}

    @app.get("/api/notes")
    def list_notes() -> list[Note]:
        with lock:
            return list(reversed(notes))

    @app.get("/api/stats")
    def stats() -> dict[str, int]:
        with lock:
            return {
                "count": len(notes),
                "longest": max((len(str(n["text"])) for n in notes), default=0),
            }

    @app.post("/api/notes", status_code=201)
    def add_note(body: NoteIn) -> Note:
        nonlocal next_id
        with lock:
            if len(notes) >= MAX_NOTES:
                raise HTTPException(status_code=409, detail="The store is full")
            note: Note = {"id": next_id, "text": body.text, "done": False}
            next_id += 1
            notes.append(note)
            return note

    @app.patch("/api/notes/{note_id}")
    def update_note(note_id: int, body: NotePatch) -> Note:
        with lock:
            for note in notes:
                if note["id"] == note_id:
                    note["done"] = body.done
                    return dict(note)
        raise HTTPException(status_code=404, detail="Note not found")

    @app.delete("/api/notes", status_code=204)
    def clear_notes() -> None:
        nonlocal next_id
        with lock:
            notes.clear()
            next_id = 1

    @app.delete("/api/notes/{note_id}", status_code=204)
    def delete_note(note_id: int) -> None:
        with lock:
            for index, note in enumerate(notes):
                if note["id"] == note_id:
                    del notes[index]
                    return
        raise HTTPException(status_code=404, detail="Note not found")

    return app
