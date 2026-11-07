# Provenance Schema

Every reference-layer row must carry the following fields.

| Field | Purpose |
|---|---|
| `concept_id` | Stable identifier referenced by code and downstream artifacts. |
| `source` | Exact source name or artifact. |
| `source_version` | Edition, release, revision, or local frozen version. |
| `source_date` | Publication, revision, or ingestion date when available. |
| `evidence_type` | Origin of the evidence. |
| `tier` | Confidence level assigned to that evidence. |
| `status` | Current operational state. |
| `notes` | Short rationale or caveat. |

## Evidence Types

- `real_observed_label`: record-level label observed directly in data.
- `validated_mapping`: source concept/text to target code mapping validated by an authoritative owner or documented rule.
- `reference_evidence`: authoritative catalog, standard, taxonomy, vocabulary, or documentation evidence.
- `expert_inference`: project inference derived from reference material or corpus behavior.
- `external_corroboration`: external evidence that supports a structural or methodological choice without validating local target mappings.
- `unknown`: unclassified evidence pending review.

## Tiers

- `gold`: directly observed or validated for measurement.
- `silver-high`: strong convergent evidence from independent sources.
- `silver-medium`: partial convergent evidence, usable with caveats.
- `unresolved`: not yet promotable.

## Critical Rule

`evidence_type` answers where the evidence comes from. `tier` answers how much confidence we place in it. These axes must never be collapsed.
