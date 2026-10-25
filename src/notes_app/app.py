"""AFAW demo notes: a tiny app that the Duo flows change through issues.

It exists so the hands-off loop has something visible to act on: an issue asks for a feature or a
fix here, the pipeline judges the merge request, and the live service shows the result. Notes are
kept in memory per instance (the service scales to zero), which is stated on the page.
"""

from __future__ import annotations

import os
import threading
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

MAX_TEXT = 200
MAX_NOTES = 100

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AFAW demo notes</title>
<style>body{font:16px system-ui;max-width:36rem;margin:2rem auto;padding:0 1rem}
li{margin:.4rem 0}small{color:#555}</style></head>
<body><h1>AFAW demo notes</h1>
<p><small>The target app of the AFAW hands-off loop: agents change it through issues.
Notes live in memory and are lost when the instance stops.</small></p>
<form id="f"><input id="t" maxlength="200" required placeholder="A note">
<button>Add</button></form><ul id="n"></ul>
<p><small id="v"></small></p>
<script>
async function load(){const r=await fetch('/api/notes');const d=await r.json();
const ul=document.getElementById('n');ul.replaceChildren();
for(const x of d){const li=document.createElement('li');li.textContent=x.text;ul.append(li)}}
document.getElementById('f').addEventListener('submit',async e=>{e.preventDefault();
const t=document.getElementById('t');
await fetch('/api/notes',{method:'POST',headers:{'content-type':'application/json'},
body:JSON.stringify({text:t.value})});t.value='';load()});
fetch('/api/version').then(r=>r.json()).then(v=>{
document.getElementById('v').textContent='Release '+v.release_tag+', commit '+v.commit_sha});
load();
</script></body></html>
"""


class NoteIn(BaseModel):
    """A note to add: trimmed text of 1 to MAX_TEXT characters, no other field."""

    model_config = ConfigDict(extra="forbid")
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)
    ]


def _env(name: str) -> str:
    """Return an environment variable, or "unknown" when it is unset or empty."""
    return os.environ.get(name) or "unknown"


def create_app() -> FastAPI:
    """Build the app with its own empty in-memory store."""
    app = FastAPI(title="AFAW demo notes")
    notes: list[dict[str, int | str]] = []
    lock = threading.Lock()

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/version")
    def version() -> dict[str, str]:
        return {"release_tag": _env("AFAW_RELEASE_TAG"), "commit_sha": _env("AFAW_COMMIT_SHA")}

    @app.get("/api/notes")
    def list_notes() -> list[dict[str, int | str]]:
        with lock:
            return list(reversed(notes))

    @app.post("/api/notes", status_code=201)
    def add_note(body: NoteIn) -> dict[str, int | str]:
        with lock:
            if len(notes) >= MAX_NOTES:
                raise HTTPException(status_code=409, detail="The store is full")
            note: dict[str, int | str] = {"id": len(notes) + 1, "text": body.text}
            notes.append(note)
            return note

    return app
