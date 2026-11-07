from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STINT2_ROOT = PROJECT_ROOT / "stint-2-target-ml-prototyping"
OUT = STINT2_ROOT / "g2_baseline_models/outputs/g20_corpus_native_domain_vocab"
CANDIDATES = OUT / "g20c_candidate_terms_sanitized.csv"
EXTERNAL_REFERENCE = OUT / "g20c_external_reference_augmentation_sanitized.csv"

FREQUENCY_FLOORS = {
    "B1_RELATIONAL": 3,
    "B2_WORKBOOKS": 2,
    "PATH_A": 1,
}

# Public adaptation: a generic library stopword set replaces the private corpus-derived list.
GENERIC_TOKENS = set(ENGLISH_STOP_WORDS)

# Supply restricted terms in the controlled environment; they are not published.
OPERATIONAL_ENTITY_TOKENS = {
    token.strip().lower()
    for token in os.environ.get("RESTRICTED_ENTITY_TOKENS", "").split(",")
    if token.strip()
}

TOKEN_RE = re.compile(r"^[a-zà-öø-ÿß]+$", re.IGNORECASE)


def tokens(term: object) -> list[str]:
    return str(term).strip().lower().split()


def is_generic_only(term: object) -> bool:
    parts = tokens(term)
    return bool(parts) and all(part in GENERIC_TOKENS for part in parts)


def has_valid_shape(term: object, declared_length: object) -> bool:
    parts = tokens(term)
    if not 1 <= len(parts) <= 3:
        return False
    if len(parts) != int(declared_length):
        return False
    if any(len(part) == 1 or TOKEN_RE.fullmatch(part) is None for part in parts):
        return False
    return True


def make_reduction_report(decisions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for path_bucket in [*FREQUENCY_FLOORS, "ALL"]:
        frame = (
            decisions
            if path_bucket == "ALL"
            else decisions[decisions["path_bucket"].eq(path_bucket)]
        )
        stages = [
            ("input", pd.Series(True, index=frame.index)),
            ("path_frequency_floor", frame["passes_path_frequency_floor"]),
            (
                "generic_only_removal",
                frame["passes_path_frequency_floor"] & frame["passes_generic_filter"],
            ),
            ("fragment_removal", frame["retained_step2"]),
        ]
        previous = len(frame)
        for order, (stage, mask) in enumerate(stages):
            surviving = int(mask.sum())
            rows.append(
                {
                    "path_bucket": path_bucket,
                    "stage_order": order,
                    "filter_stage": stage,
                    "terms_entering_stage": previous if order else len(frame),
                    "terms_removed_at_stage": 0 if order == 0 else previous - surviving,
                    "terms_surviving_stage": surviving,
                    "survival_pct_of_input": round(
                        100 * surviving / len(frame), 6
                    )
                    if len(frame)
                    else 0.0,
                    "frequency_floor": (
                        FREQUENCY_FLOORS.get(path_bucket, "path_specific")
                    ),
                    "target_assignment": "deferred_to_step3_semantic_grouping",
                }
            )
            previous = surviving
    return pd.DataFrame(rows)


def main() -> None:
    candidates = pd.read_csv(CANDIDATES).fillna("")
    required = {
        "target",
        "path_bucket",
        "candidate_term",
        "ngram_length",
        "units_with_term",
        "construction_universe",
        "normalisation_pipeline",
        "construction_method",
    }
    missing = required - set(candidates.columns)
    if missing:
        raise RuntimeError(f"Missing candidate columns: {sorted(missing)}")
    if set(candidates["path_bucket"]) != set(FREQUENCY_FLOORS):
        raise RuntimeError("Unexpected path buckets in Step 1 candidate pool")
    if set(candidates["target"]) != {"unassigned"}:
        raise RuntimeError("Step 2 requires the target-neutral Step 1 pool")
    if set(candidates["construction_universe"]) != {
        "model_eligible_construction_corpus"
    }:
        raise RuntimeError("Step 2 must use only the model-eligible construction corpus")
    if set(candidates["normalisation_pipeline"]) != {"semantic_normalisation_v2"}:
        raise RuntimeError("Unexpected normalization pipeline")

    candidate_tokens = {
        token
        for term in candidates["candidate_term"]
        for token in tokens(term)
    }
    leaked_entities = sorted(candidate_tokens & OPERATIONAL_ENTITY_TOKENS)
    if leaked_entities:
        raise RuntimeError(f"Operational tokens remain in Step 1 pool: {leaked_entities}")

    candidates["path_frequency_floor"] = candidates["path_bucket"].map(
        FREQUENCY_FLOORS
    )
    candidates["passes_path_frequency_floor"] = (
        pd.to_numeric(candidates["units_with_term"], errors="raise")
        >= candidates["path_frequency_floor"]
    )
    candidates["generic_only_term"] = candidates["candidate_term"].map(
        is_generic_only
    )
    candidates["passes_generic_filter"] = ~candidates["generic_only_term"]
    candidates["valid_term_shape"] = candidates.apply(
        lambda row: has_valid_shape(row["candidate_term"], row["ngram_length"]),
        axis=1,
    )
    candidates["passes_fragment_filter"] = candidates["valid_term_shape"]
    candidates["retained_step2"] = (
        candidates["passes_path_frequency_floor"]
        & candidates["passes_generic_filter"]
        & candidates["passes_fragment_filter"]
    )
    candidates["step2_decision"] = "retained_for_semantic_grouping"
    candidates.loc[
        ~candidates["passes_fragment_filter"], "step2_decision"
    ] = "excluded_fragment_or_invalid_length"
    candidates.loc[
        ~candidates["passes_generic_filter"], "step2_decision"
    ] = "excluded_generic_only_term"
    candidates.loc[
        ~candidates["passes_path_frequency_floor"], "step2_decision"
    ] = "excluded_below_path_frequency_floor"
    candidates["step2_method"] = "path_specific_frequency_and_neutral_lexical_filter_v1"
    candidates["target_assignment"] = "deferred_to_step3_semantic_grouping"
    candidates["external_reference_layer_merged"] = False

    retained = candidates[candidates["retained_step2"]].copy()
    retained["grouping_status"] = "pending_step3_semantic_grouping"
    retained["mapping_status"] = "not_mapped"
    retained = retained.sort_values(
        ["path_bucket", "units_with_term", "ngram_length", "candidate_term"],
        ascending=[True, False, True, True],
    )
    decisions = candidates.sort_values(
        ["path_bucket", "retained_step2", "units_with_term", "candidate_term"],
        ascending=[True, False, False, True],
    )
    reduction = make_reduction_report(decisions)

    rules = pd.DataFrame(
        [
            {
                "rule_id": f"frequency_floor_{path.lower()}",
                "rule_type": "path_specific_frequency_floor",
                "path_bucket": path,
                "value": floor,
                "scope": "corpus_native_candidates_only",
                "rationale": (
                    "retain all because eligible frequency is not a prevalence estimate"
                    if path == "PATH_A"
                    else "remove sparse terms before semantic grouping"
                ),
            }
            for path, floor in FREQUENCY_FLOORS.items()
        ]
        + [
            {
                "rule_id": "generic_only_term",
                "rule_type": "generic_stopword_removal",
                "path_bucket": "ALL",
                "value": "all tokens generic",
                "scope": "corpus_native_candidates_only",
                "rationale": "retain mixed phrases when any non-generic token is present",
            },
            {
                "rule_id": "fragment_or_invalid_length",
                "rule_type": "shape_filter",
                "path_bucket": "ALL",
                "value": "1-3 alphabetic tokens; no one-character fragments",
                "scope": "corpus_native_candidates_only",
                "rationale": "remove fragments without assigning Activity or Object Part",
            },
            {
                "rule_id": "external_reference_separation",
                "rule_type": "governance_guard",
                "path_bucket": "ALL",
                "value": "not frequency filtered or merged",
                "scope": "external_reference_layer",
                "rationale": "external evidence can support Step 3 coverage only",
            },
        ]
    )

    if not EXTERNAL_REFERENCE.exists():
        raise RuntimeError("External reference augmentation artefact is missing")
    external = pd.read_csv(EXTERNAL_REFERENCE).fillna("")
    external_frequency_eligible = (
        external["eligible_for_frequency_filter"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes"})
    )
    if external.empty or external_frequency_eligible.any():
        raise RuntimeError("External reference frequency-filter guard failed")
    if len(decisions) != len(candidates):
        raise RuntimeError("Step 2 decision parity failed")
    if decisions.duplicated(["path_bucket", "candidate_term"]).any():
        raise RuntimeError("Duplicate term detected within a path")
    if retained["external_reference_layer_merged"].any():
        raise RuntimeError("External reference rows were merged into corpus-native output")
    if retained.empty:
        raise RuntimeError("Step 2 unexpectedly removed every term")

    retained.to_csv(
        OUT / "g20c_filtered_terms_sanitized.csv", index=False, lineterminator="\n"
    )
    decisions.to_csv(
        OUT / "g20c_filter_decisions_sanitized.csv", index=False, lineterminator="\n"
    )
    reduction.to_csv(
        OUT / "g20c_filter_reduction_report_sanitized.csv",
        index=False,
        lineterminator="\n",
    )
    rules.to_csv(
        OUT / "g20c_step2_filter_rules_sanitized.csv",
        index=False,
        lineterminator="\n",
    )

    final_counts = retained.groupby("path_bucket").size().to_dict()
    input_counts = candidates.groupby("path_bucket").size().to_dict()
    memo = f"""# G2.0c Step 2 - Filtering

## Scope

Filtering only. No target assignment, semantic grouping, catalogue mapping,
candidate promotion, denominator change, or model re-run occurred.

## Path-specific frequency floors

- B1_RELATIONAL: 3 eligible units.
- B2_WORKBOOKS: 2 eligible units.
- PATH_A: 1 eligible unit. Path A frequency is not a prevalence estimate after
  evaluation exclusions, so singletons are retained when they pass lexical filters.

## Result

- Input terms: {len(candidates):,}.
- Retained terms: {len(retained):,}.
- Input by path: {input_counts}.
- Retained by path: {final_counts}.

The generic filter removes a phrase only when every token is generic. Mixed phrases
remain available for Step 3. The shape filter removes one-character fragments and
terms outside the declared 1-3 alphabetic-token format.

## External reference layer

The {len(external)} admitted external reference terms remain in their separate
artefact. They were not merged, frequency-filtered, or counted in the reduction
curve. Step 3 may use them only as explicitly sourced coverage evidence.

## Governance

- Construction universe: model_eligible_construction_corpus.
- Normalisation: semantic_normalisation_v2.
- Target remains unassigned until Step 3 semantic grouping.
- Evaluation text was not used.
- Raw operational values emitted: false.
"""
    (OUT / "g20c_step2_filtering_memo.md").write_text(memo, encoding="utf-8")

    print(reduction.to_string(index=False))
    print(f"retained_rows={len(retained)} external_reference_rows={len(external)}")


if __name__ == "__main__":
    main()
