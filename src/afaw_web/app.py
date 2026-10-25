"""The read-only FastAPI application: GET endpoints only, nothing is ever written.

Endpoints are plain functions (FastAPI runs them in its thread pool), so reading a file never
blocks the event loop. A missing view is an explicit 503, never an empty answer that looks fine.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import AfterValidator
from pydantic_core import PydanticCustomError

from afaw_web.search import search
from afaw_web.settings import Settings

log = logging.getLogger("afaw_web")
VIEWS = ("metrics", "pending", "history")
MIN_QUESTION, MAX_QUESTION = 1, 200
QUESTION_LIMIT = (
    f"The question: between {MIN_QUESTION} and {MAX_QUESTION} characters after trimming "
    "leading and trailing whitespace; anything else is rejected with 422."
)


def _check_question_length(question: str) -> str:
    """Return the question unchanged if its trimmed length is within the limit.

    The error types and context match the built-in ``min_length``/``max_length`` ones.
    """
    size = len(question.strip())
    if size < MIN_QUESTION:
        raise PydanticCustomError(
            "string_too_short",
            "must have at least {min_length} characters after trimming whitespace",
            {"min_length": MIN_QUESTION},
        )
    if size > MAX_QUESTION:
        raise PydanticCustomError(
            "string_too_long",
            "must have at most {max_length} characters after trimming whitespace",
            {"max_length": MAX_QUESTION},
        )
    return question


Question = Annotated[
    str,
    AfterValidator(_check_question_length),
    Query(
        description=QUESTION_LIMIT,
        json_schema_extra={"minLength": MIN_QUESTION, "maxLength": MAX_QUESTION},
    ),
]


async def _invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
    """A 422 whose messages start with the name of the offending parameter."""
    detail = [
        {
            "loc": list(e["loc"]),
            "msg": f"{e['loc'][-1]}: {e['msg']}",
            "type": e["type"],
            **({"ctx": e["ctx"]} if "ctx" in e else {}),
        }
        for e in exc.errors()
    ]
    return JSONResponse({"detail": detail}, status_code=422)


def _missing(data_dir: Path) -> list[str]:
    needed = [f"live/{v}.json" for v in VIEWS] + ["live/dashboard.html", "demo/index.html"]
    return [name for name in needed if not (data_dir / name).is_file()]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application over the data directory in ``settings``."""
    data_dir = (settings or Settings()).data_dir
    app = FastAPI(title="AFAW Hands-off", docs_url=None, redoc_url=None)
    app.add_exception_handler(RequestValidationError, _invalid_request)  # type: ignore[arg-type]

    def unavailable(missing: list[str]) -> JSONResponse:
        log.error("data missing: %s", missing)
        return JSONResponse({"status": "unavailable", "missing": missing}, status_code=503)

    @app.get("/health", response_model=None)
    def health() -> dict[str, str] | JSONResponse:
        """Ok only when every baked-in view is present."""
        missing = _missing(data_dir)
        return unavailable(missing) if missing else {"status": "ok"}

    @app.get("/api/state", response_model=None)
    def state() -> dict[str, Any] | JSONResponse:
        """The derived metrics, pending tasks and history, exactly as the engine wrote them."""
        missing = [m for m in _missing(data_dir) if m.endswith(".json")]
        if missing:
            return unavailable(missing)
        return {v: json.loads((data_dir / "live" / f"{v}.json").read_text("utf-8")) for v in VIEWS}

    @app.get("/", response_class=HTMLResponse, response_model=None)
    def demo() -> HTMLResponse | JSONResponse:
        """The demo dashboard, built from invented mock data."""
        return _page(data_dir / "demo" / "index.html", unavailable)

    @app.get("/live/", response_class=HTMLResponse, response_model=None)
    def live() -> HTMLResponse | JSONResponse:
        """This repository's own dashboard."""
        return _page(data_dir / "live" / "dashboard.html", unavailable)

    @app.get("/api/ask")
    def ask(q: Question) -> dict[str, Any]:
        """Search the ADRs, gotchas and LASTCONTEXT; cite paths; copy lines verbatim."""
        hits = search(data_dir, q)
        return {
            "query": q,
            "message": "" if hits else "no record contains any word of the question",
            "results": [
                {"path": h.path, "title": h.title, "excerpts": h.excerpts, "score": h.score}
                for h in hits
            ],
        }

    return app


def _page(path: Path, unavailable: Any) -> HTMLResponse | JSONResponse:
    if not path.is_file():
        response: JSONResponse = unavailable([path.parent.name + "/" + path.name])
        return response
    return HTMLResponse(path.read_text(encoding="utf-8"))
