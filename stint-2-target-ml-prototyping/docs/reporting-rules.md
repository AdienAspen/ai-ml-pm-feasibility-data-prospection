# Reporting Rules

## Mandatory Qualifiers

Every reported metric must state:

- `evaluation_set_type`
- `n`
- `path`
- `threshold`

## Forbidden

STINT 2 reports must not include:

- aggregation across paths
- bare `accuracy = X`
- comparison to an external contractual accuracy target
- metrics against `derived_from_rules` labels without a circularity caveat

## Required Alongside

Every model result must report:

- macro F1 whenever weighted F1 is reported
- coverage whenever precision is reported
- abstention rate per target

## Boundary

Before independent evaluation exists, report only readiness, evidence availability, class distribution, annotation progress, and blockers.
