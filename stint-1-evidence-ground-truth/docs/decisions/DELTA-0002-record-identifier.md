# Decision: record identity for denominator counting

## Issue

A source row, a text field, a candidate, and a physical maintenance record are different counting units. A denominator needs a stable identity that survives expansion into multiple evidence rows.

## Decision

The evidence register uses two related, non-reversible identifiers:

- `physical_record_id` identifies a source record for target-level counting.
- `record_field_id` identifies the same record with a specific text field for evidence tracing.

The physical key is derived from controlled source lineage; the record-field key additionally includes `source_text_field`. The implementation must not publish business identifiers or raw source paths.

For a target, denominator `N` is the number of unique `physical_record_id × target` pairs. Multiple convergent evidence rows from one record count once. Row, file, and candidate counts are never substituted for this denominator.

The reported figure also declares source path, stratum, evidence type, tier, and whether the denominator is contractual or proxy evidence. Incompatible paths are not aggregated.
