# Denominator Policy

## Rules

- Never use a global denominator for the PoC.
- Denominators are target-specific.
- The denominator count `N` is unique physical records per target, not evidence rows.
- Multiple convergent evidence rows for the same physical record and target count once.
- `stint1_record_id` may identify a `record-field` evidence unit for traceability, but denominator outputs must deduplicate to `physical_record_id x target`.
- `physical_record_id` is generated from sanitized source lineage without `source_text_field`.
- Evidence supported by a daily snapshot event carries an `event_structural` stratum. If combined with structured evidence, counts must be split by stratum or explicitly marked as mixed-source support.
- Strata are not mixed.
- A zero denominator is a valid feasibility result.
- Denominators must be reported as:

```text
target x denominator_type x evidence_type x tier x contractor_path x site_key x stratum
```

## Denominator Types

### Contractual Denominator

All conditions are required:

- `evidence_type` is `real_observed_label` or `validated_mapping`
- `tier` is `gold`
- `status` is `resolved`

`expert_inference`, `reference_evidence`, `external_corroboration`, `synthetic`, `proxy_label`, and `unresolved` are excluded without exception. This is the only denominator that could support a contractual production-accuracy claim.

### POC Proxy Denominator

This denominator may include qualified surrogate evidence, including `silver-high`, qualified `silver-medium`, and `expert_inference`, only when provenance is complete and the target destination is valid.

`expert_inference` enters the proxy denominator only if all are true:

- stable and resolvable `concept_id`
- documented reproducible derivation rule
- declared source and `source_text_field`
- valid destination in the documented canonical contract
- explicit tier rationale
- `label_generation_method` declared
- `evaluation_independence` declared

## Evaluation Independence

A held-out proxy evaluation set must use records marked `evaluation_independence = independent`, or must explicitly exclude the rule set that generated labels from the predictor being evaluated.

If the same rule set generates a label and later predicts it, the result is circular and cannot be reported as model accuracy.

## Accuracy Boundary

Do not estimate model accuracy, coverage, or contractual performance until a defensible measurement denominator exists for the target being assessed.
