# Sustainability paragraph for Devpost

Drop-in text. Replace the bracketed part with the measured result once the experiment has run; until
then, use only the first paragraph.

## Current text (no data yet)

AFAW Hands-off has not measured its energy or carbon effect yet. We use the Software Carbon
Intensity specification (version 1.1.0, published as ISO/IEC 21031:2024) as the method, per merged
merge request, and we list every assumption: GitLab's hosted runners run in Google Cloud
`us-east1` and `us-east5` (2025 grid intensity 579 and 343 gCO2eq/kWh), the power per vCPU comes
from the Cloud Carbon Footprint methodology, and embodied emissions are not estimated, so any score
is an "SCI without M". Gains described elsewhere in this project are expected, not measured.
Method and limits: [ADR 0009](../adr/0009-measure-sustainability-with-sci.md).

## Text after the experiment

[Three small tasks were done in two modes. Per merged merge request, the naive mode used
X kWh to Y kWh and AFAW used X kWh to Y kWh, with the assumptions and the limits stated in
ADR 0009. This is three tasks on shared runners with assumed power and makes no statistical
claim.]

## Decision rule

We opt in to the Most Environmentally Impactful prize only if the experiment is completed with
data and every assumption listed. The decision is on 2026-10-25 at 18:00 GMT-3.
