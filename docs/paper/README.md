# Paper

- **PDF:** [`afaw.pdf`](afaw.pdf), committed with every change to its sources.
- **Source:** `afaw.tex`. Its appendix is generated from `AGENTS.md`, so the rules exist in one place
  only; the figures are the ones in `docs/img/`, rendered from `docs/diagrams/*.dot`.

Rebuild without installing LaTeX: the `paper_build` job of `.gitlab-ci.yml` compiles the paper in a pinned TeX Live image; download its artifact `docs/paper/afaw.pdf`. Or rebuild locally (XeLaTeX, Liberation Sans or Arial installed). Then commit `afaw.pdf` in the same pull
request as the source change. CI fails a pull request that changes `afaw.tex`, `AGENTS.md` or
`docs/img/` without changing the PDF
([gotcha 0002](../gotchas/0002-committed-pdf-drifts-from-its-source.md)).

```bash
python -m scripts.rules_to_tex AGENTS.md docs/paper/appendix_rules.tex
cd docs/paper
xelatex afaw.tex && xelatex afaw.tex
```

`appendix_rules.tex` and the LaTeX build files are generated and ignored by git. The archived
version is on Zenodo: https://doi.org/10.5281/zenodo.23050310
