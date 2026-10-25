"""Project name, logo, author footer and the live GitLab panel of the dashboard.

Everything here is static text: the page loads nothing from another site except the public GitLab
REST API v4 that the live panel reads in the browser, with no token. The logo is a simple mark
drawn for this page, not an official asset.
"""

from __future__ import annotations

NAME = "AFAW Engine Gitlab"
AUTHOR = "Agustin Diaz-Cano"
PORTFOLIO = "https://www.agustindiazcano.com/"
REPOSITORY = "https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase"
API = (
    "https://gitlab.com/api/v4/projects/"
    "gitlab-ai-hackathon%2Ftranscend-october-2026%2F43344247%2Fshowcase"
)
REFRESH_MS = 30000

LOGO = (
    '<svg class="logo" viewBox="0 0 32 32" role="img" aria-label="GitLab" width="28" height="28">'
    "<title>GitLab</title>"
    '<polygon fill="#e24329" points="16,29 3,19 7,6 11,15 21,15 25,6 29,19"/>'
    '<polygon fill="#fc6d26" points="3,19 11,15 16,29"/>'
    '<polygon fill="#fc6d26" points="29,19 21,15 16,29"/>'
    '<polygon fill="#fca326" points="7,6 11,15 3,19"/>'
    '<polygon fill="#fca326" points="25,6 21,15 29,19"/>'
    "</svg>"
)

CSS = """
.top{background:var(--card);border-bottom:1px solid var(--line)}
.top nav{max-width:1200px;margin:0 auto;padding:10px 16px;display:flex;flex-wrap:wrap;
  align-items:center;gap:8px 20px}
.brand{display:inline-flex;align-items:center;gap:10px;font-weight:700;font-size:16px;
  text-decoration:none}
.top nav a.item{text-decoration:none;color:var(--muted)}
.top nav a.item:hover{color:var(--ink);text-decoration:underline}
.top nav .spacer{flex:1}
footer.site{max-width:1200px;margin:0 auto;padding:16px;border-top:1px solid var(--line);
  color:var(--muted);display:flex;flex-wrap:wrap;gap:8px 24px;justify-content:space-between}
#live .counters{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px}
#live .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;
  margin-top:12px}
#live ul{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);
  border-radius:8px}
#live li{padding:8px 12px;border-top:1px solid var(--line);display:flex;gap:10px;
  align-items:baseline}
#live li:first-child{border-top:0}
#live .tag{font-size:12px;border:1px solid var(--line);border-radius:10px;padding:0 8px;
  white-space:nowrap}
#live .ok{color:var(--green)}
#live .bad{color:var(--red)}
#live .wait{color:var(--yellow)}
#live .stamp{color:var(--muted);font-size:12px}
"""

_SCRIPT = """
(function () {
  var API = "__API__";
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function get(path) {
    return fetch(API + path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json().then(function (data) {
        return { data: data, total: Number(r.headers.get("X-Total")) };
      });
    });
  }
  function counter(box, value, label) {
    var tile = el("div", "tile");
    tile.appendChild(el("b", "", String(value)));
    tile.appendChild(el("span", "", label));
    box.appendChild(tile);
  }
  function tone(status) {
    if (status === "success" || status === "merged") return "ok";
    if (status === "failed" || status === "closed" || status === "canceled") return "bad";
    return "wait";
  }
  function fill(list, rows) {
    list.textContent = "";
    rows.forEach(function (row) {
      var li = el("li");
      li.appendChild(el("span", "tag " + row.tone, row.tag));
      li.appendChild(el("span", "", row.text));
      list.appendChild(li);
    });
  }
  function refresh() {
    Promise.all([
      get("/merge_requests?state=merged&per_page=1"),
      get("/merge_requests?state=opened&per_page=1"),
      get("/pipelines?source=duo_workflow&per_page=1"),
      get("/pipelines?status=success&per_page=1"),
      get("/pipelines?status=failed&per_page=1"),
      get("/merge_requests?state=all&order_by=updated_at&per_page=8"),
      get("/pipelines?per_page=8")
    ]).then(function (r) {
      var box = document.getElementById("live-counters");
      box.textContent = "";
      counter(box, r[0].total, "Merge requests merged");
      counter(box, r[1].total, "Merge requests open");
      counter(box, r[2].total, "Duo flow sessions");
      counter(box, r[3].total, "Pipelines passed");
      counter(box, r[4].total, "Pipelines failed");
      fill(document.getElementById("live-mrs"), r[5].data.map(function (m) {
        var state = m.draft && m.state === "opened" ? "draft" : m.state;
        return { tag: state, tone: tone(m.state), text: "!" + m.iid + " " + m.title };
      }));
      fill(document.getElementById("live-pipelines"), r[6].data.map(function (p) {
        var who = p.source === "duo_workflow" ? "Duo flow" : p.source;
        return { tag: p.status, tone: tone(p.status), text: "#" + p.id + " " + who };
      }));
      document.getElementById("live-stamp").textContent =
        "Updated " + new Date().toLocaleTimeString() + " from the public GitLab API";
    }).catch(function (err) {
      document.getElementById("live-stamp").textContent =
        "The GitLab API did not answer (" + err.message + "); retrying";
    });
  }
  refresh();
  setInterval(refresh, __REFRESH__);
})();
""".replace("__API__", API).replace("__REFRESH__", str(REFRESH_MS))


def nav() -> str:
    """The top bar: logo, name and the links to the views and the repository."""
    return (
        '<header class="top"><nav aria-label="Main">'
        f'<a class="brand" href="/live/">{LOGO}<span>{NAME}</span></a>'
        '<a class="item" href="/live/">Dashboard</a>'
        '<a class="item" href="/">Demo</a>'
        '<a class="item" href="/api/state">State API</a>'
        f'<a class="item" href="{REPOSITORY}/-/blob/main/docs/submission/evidence.md">Evidence</a>'
        '<span class="spacer"></span>'
        f'<a class="item" href="{REPOSITORY}" rel="noopener">Repository</a>'
        "</nav></header>"
    )


def footer() -> str:
    """The author line, with the link to the portfolio."""
    return (
        '<footer class="site"><span>'
        f'Author: <a href="{PORTFOLIO}" rel="noopener noreferrer">{AUTHOR}</a></span>'
        f"<span>{NAME} · MIT licence · built for the GitLab Transcend hackathon</span></footer>"
    )


def live_panel() -> str:
    """A panel that reads the public GitLab API in the browser and refreshes every 30 seconds."""
    return (
        '<section id="live"><h2>Live from GitLab</h2>'
        '<noscript><p class="warn">This panel needs JavaScript. The rest of the page does not.'
        "</p></noscript>"
        '<div id="live-counters" class="counters"></div>'
        '<div class="cols"><div><h3>Merge requests</h3><ul id="live-mrs"></ul></div>'
        '<div><h3>Pipelines</h3><ul id="live-pipelines"></ul></div></div>'
        '<p id="live-stamp" class="stamp">Loading…</p>'
        f"<script>{_SCRIPT}</script></section>"
    )
