---
status: proposed
date: 2026-10-24
supersedes: []
tags: [sustainability, sci, ci, measurement]
---
# Measure sustainability with the Software Carbon Intensity, per merged merge request

## Context
The README says the energy and carbon effect of the loop is "not yet measured", and
`AGENTS.md` forbids a saving, speed, cost or carbon figure without a measurement. A figure needs a
method that others can check. The Software Carbon Intensity (SCI) specification is that method.

Facts checked on 2026-10-24:

| Fact | Source |
|---|---|
| The SCI specification is version 1.1.0: SCI = (O + M) per R, with O = E x I | [sci.greensoftware.foundation](https://sci.greensoftware.foundation/) |
| That page does not state an ISO or IEC number; it says "There are no normative references in this document" | the same page |
| The standard is published as ISO/IEC 21031:2024, "Information technology - Software Carbon Intensity (SCI) specification", edition 1.0, 2024-03-22 | [IEC webstore](https://webstore.iec.ch/publication/93436) |
| I must be a grid intensity (average or marginal) and excludes market-based measures | the specification page |
| M must include an estimate of all embodied emissions of the hardware inside the software boundary | the specification page |
| GitLab.com hosted Linux x86-64 runners run on Google Cloud Compute Engine in `us-east1` and `us-east5`; the default `small` runner has 2 vCPUs and 8 GB | [Hosted runners on Linux](https://docs.gitlab.com/ee/ci/runners/hosted_runners/linux.html) |
| Google Cloud region data for 2025, grid carbon intensity: `us-east1` 579, `us-east5` 343, `us-central1` 432 gCO2eq/kWh. It is "the average operational gross emissions per unit of energy from the grid". The page does not say whether the figure is location-based or market-based | [Google Cloud region carbon data](https://cloud.google.com/sustainability/region-carbon) |
| The Cloud Carbon Footprint methodology gives, for GCP, a median of 0.71 W (minimum) to 4.26 W (maximum) per vCPU, a PUE of 1.1 and the formula Average Watts = Min + Utilization x (Max - Min). It gives no numeric embodied value | [Cloud Carbon Footprint methodology](https://www.cloudcarbonfootprint.org/docs/methodology/) |
| GitLab documents no REST or GraphQL endpoint for GitLab Credits usage; the only export is in the Customers Portal and needs a billing account manager | [GitLab Credits dashboard](https://docs.gitlab.com/subscriptions/gitlab_credits_dashboard/) |

## Decision
Report the SCI of the development loop with R = one merged merge request, computed by a
script from measured job durations plus labelled assumptions. Every term is either measured, with
its source and tool, or assumed, with its value, source and uncertainty:

| Term | Status | Value or source | Uncertainty |
|---|---|---|---|
| R | Defined | One merged merge request | None |
| Job seconds of the merge request's pipelines | MEASURED | GitLab REST API v4 via `scripts.cost_log` (`duration` of each job, retries included) | The runner's real utilization is not visible |
| E | ASSUMED from the measurement | job seconds / 3600 x 2 vCPUs x W per vCPU x PUE. W per vCPU: report the range 0.71 to 4.26 and, at the methodology's 50% utilization default, 2.485 W. PUE 1.1. All from the Cloud Carbon Footprint page | The range spans a factor of about 6; the machine type (2 vCPUs) is from GitLab's documentation, not read from each job |
| I | CITED | 343 (`us-east5`) to 579 (`us-east1`) gCO2eq/kWh, 2025. The API does not tell which of the two regions ran a job, so both are reported | The Google page does not label the figure location-based or market-based; the spec excludes market-based |
| M | NOT ESTIMATED | No published embodied figure for the runner machine type was found. The specification says M shall be included, so a score without M is labelled "SCI without M" and is not claimed to conform | Unknown |

The Cloud Run service (`us-central1`, 432 gCO2eq/kWh) serves the demo, not a merge request, so it is
outside R and reported apart if at all. The energy of the LLM inference behind GitLab Duo is not
measured and no figure is used for it; GitLab Credits are an accounting unit, not energy.

## Experiment
The same three small code tasks are done in two modes, chosen and listed before the run.

| Mode | What the agent does | Measured per task |
|---|---|---|
| A, "naive agent" | Runs the full test suite locally after each edit and retries until green | Local wall-clock seconds of the full suite, number of runs, retries |
| B, "AFAW" | Runs only its own test locally; CI runs everything once | Local seconds of its own test; from the public API, CI job minutes, job seconds, pipelines and retries (`scripts.cost_log` and the `collect_facts` parsers) |

Energy and SCI per merged merge request, for both modes, with every assumption listed:

| Term | Mode A | Mode B |
|---|---|---|
| E, local | local seconds x laptop power | local seconds of its own test x laptop power |
| E, CI | none | job seconds / 3600 x 2 vCPUs x 0.71 to 4.26 W x 1.1 (Cloud Carbon Footprint) |
| Laptop power | ASSUMED 9 to 22 W: 9 to 13 W measured during browser interactions and 15 to 22 W as the fixed values of current reporting models ([Kirkeby and Lagermann, arXiv:2510.12566](https://arxiv.org/abs/2510.12566)). A test run is CPU-bound, so the real value may be higher; the study did not test it | same |
| I | 343 to 579 gCO2eq/kWh (`us-east5` and `us-east1`), applied to both modes | same |
| M | Excluded; the result is labelled "SCI without M" | same |

The laptop's own grid is not used, because no verified figure for its location was collected;
applying the same I range to both modes keeps the comparison on energy. Tokens are recorded only
if a Duo session exposes them. GitLab documents token counts in the per-event usage export, which
needs a billing account manager ([GitLab Credits dashboard](https://docs.gitlab.com/subscriptions/gitlab_credits_dashboard/));
when it is not available the field reads "not measurable".

Limits: three tasks, shared runners whose region and utilization are not visible, assumed power
for both machines, no statistical claim. The experiment cannot show the energy of the model
inference behind either agent, how the result scales to other projects, or the effect of
a different laptop. The README keeps "not yet measured" until data exists, and the Most
Environmentally Impactful prize is requested only if the experiment is completed with data and
every assumption listed.

## Alternatives considered
- **Estimate energy from GitLab Credits.** Rejected: no source relates credits to kWh.
- **Use the market-based Google figure (Google CFE%).** Rejected: the specification excludes
  market-based measures from I.
- **Pick one runner region.** Rejected: nothing in the API says which region ran a job, so
  choosing one would be a guess; the range is reported instead.
- **State an estimated M anyway.** Rejected: no sourced figure was found; an unsourced number
  would break the rule that every figure is measured or cited.

## Consequences
- The README keeps "not yet measured" until a run of the method produces data.
- Results are ranges with the assumptions beside them, not single numbers.
- The score is an "SCI without M" until a published embodied figure for the runner is found.
- Revisit if GitLab publishes the runner region per job, a credit-to-energy relation or an
  embodied figure for its machine types.
