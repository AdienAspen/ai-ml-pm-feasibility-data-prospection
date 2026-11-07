# Evidence Provenance Schema

## Purpose

This schema extends the STINT_1.1 provenance model with record-level fields needed for evidence reconstruction.

## Required Fields

| field | meaning |
|---|---|
| `record_id` | Stable record identifier or documented proxy. |
| `physical_record_id` | Stable proxy for the physical source record before `source_text_field` expansion. Required for denominator counting. |
| `target` | One of the seven project targets. |
| `evidence_type` | Provenance/type of evidence. |
| `tier` | Confidence tier. |
| `status` | Promotion state. |
| `source_path` | Sanitized source path or source family key. |
| `source_text_field` | Text/runtime field from which evidence was extracted. |
| `stratum` | Maintenance-type or event-structural stratum. |
| `site_key` | Sanitized site key. |
| `contractor_path` | Sanitized contractor/path key. |
| `concept_id` | Stable reference-layer or STINT_1 concept id. |
| `confidence` | Numeric or categorical confidence, if defensible. |
| `label_generation_method` | Method that produced the label or candidate label, for example `observed`, `manual`, `rule_set_id`, or `derivation_rule`. |
| `evaluation_independence` | Evaluation independence flag: `independent`, `derived_from_rules`, or `unknown`. |
| `notes` | Sanitized methodological note, never raw operational text. |


## External Code Handling

External equipment and event codes must be parsed and persisted as strings, not numeric values. Leading zeros can be significant and must be preserved end to end. Any parser, CSV reader, spreadsheet reader, or aggregation step that touches these fields must force text/string dtype before hashing, grouping, joining, or counting.

Required fields for a code dictionary:

| field | rule |
|---|---|
| `code` | Internal-only raw code string, preserving leading zeros. |
| `code_hash` | Versionable stable hash derived from the exact raw code string. |
| `raw_description` | Internal-only observed description exactly as extracted, subject to internal access controls. |
| `normalised_description` | Internal-only normalized description used for semantic comparison. |
| `normalised_description_hash` | Versionable stable hash derived from the normalized description. |

Never coerce external codes to integer or float. A code with leading zeros becoming shorter is a silent collision risk.

## Evidence Types

- `real_observed_label`
- `validated_mapping`
- `reference_evidence`
- `external_corroboration`
- `expert_inference`
- `synthetic`
- `proxy_label`
- `unresolved`

## Tiers

- `gold`
- `silver-high`
- `silver-medium`
- `unresolved`

## Non-Negotiable Rule

`evidence_type` and `tier` are independent axes. Do not encode source provenance inside confidence tier.

## Evaluation Independence

Evidence used to generate a proxy label must declare how that label was produced and whether it is independent from the rule set that may later be evaluated.

`evaluation_independence = independent` is required for a held-out proxy evaluation set unless the evaluated rule set is explicitly excluded from the predictor under test. Labels marked `derived_from_rules` may support development and audit, but they cannot be used to claim model performance against the same logic that generated them.
