# Anchor Source Policy

## Anchor Source Values

`anchor_source` must be one of:

- `domain_vocabulary`
- `sap_catalog`
- `structural_field`

## Rule

`anchor_source` is a first-line filter, not a post-hoc check.

`sap_catalog` anchors over-generate because catalog entries are encoded descriptions, not technician language.

## Interpretation

Catalog-derived anchors can over-generate candidates because encoded catalog descriptions differ from maintenance narratives. Measure their contribution separately from domain vocabulary and structural fields.

## Required

- `anchor_source` must be present on every feature row.
- Error analysis must be broken down by `anchor_source`.

## Boundary

Anchor sources may route feature generation and review. They do not create independent labels by themselves.
