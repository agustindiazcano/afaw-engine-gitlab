"""The ecological indicator at the top of the dashboard, from the output of scripts.sci_report.

Only what was measured is shown: a per-flow range of gCO2eq, the number of flows and the job
seconds behind it, and what the figure leaves out. With no flows it says nothing was measured.
"""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

TITLE = "<h1>Project status</h1>"


def indicator(sci: Mapping[str, Any]) -> str:
    """HTML block with the per-flow SCI range, or a statement that nothing was measured."""
    flows = int(sci["flows"])
    if flows == 0:
        return '<p class="banner eco">Carbon: No flow measured yet.</p>'
    low = float(sci["gco2eq_low"]) / flows
    high = float(sci["gco2eq_high"]) / flows
    return (
        '<p class="banner eco">Carbon of one flow (a merged merge request through the pipeline): '
        f"{low:.2f} to {high:.2f} gCO2eq, over {flows} merged merge requests "
        f"({float(sci['job_seconds']):.0f} job seconds). "
        f"{escape(str(sci['assumptions']))}. The range comes from stated power and grid "
        'assumptions; see the <a href="/environment/">environment page</a>.</p>'
    )


def inject(page: str, sci: Mapping[str, Any]) -> str:
    """Put the indicator right after the page title; a page without the title is unchanged."""
    if TITLE not in page:
        return page
    return page.replace(TITLE, TITLE + indicator(sci), 1)
