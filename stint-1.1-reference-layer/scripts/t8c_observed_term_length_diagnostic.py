from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STINT_ROOT = PROJECT_ROOT / "stint-1.1-reference-layer"
LEXICAL_DIR = STINT_ROOT / "reference_layer" / "lexical_layer"
OUTPUTS_DIR = STINT_ROOT / "outputs"
DOCS_DIR = STINT_ROOT / "docs"

RAW_DICTIONARY = LEXICAL_DIR / "lexical_seed_dictionary_v1.csv"
SUMMARY_PATH = OUTPUTS_DIR / "t8c_observed_term_length_diagnostic_v1.json"
MEMO_PATH = DOCS_DIR / "t8c_observed_term_length_diagnostic.md"


def word_count(value: object) -> int:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    return len([token for token in re.split(r"\s+", text) if token])


def pct(mask: pd.Series) -> float:
    return round(float(mask.mean() * 100), 2) if len(mask) else 0.0


def counter_to_dict(counter: Counter) -> dict[str, int]:
    return {str(key): int(value) for key, value in sorted(counter.items(), key=lambda item: item[0])}


def main() -> None:
    if not RAW_DICTIONARY.exists():
        raise FileNotFoundError(f"Missing local-only working dictionary: {RAW_DICTIONARY}")

    df = pd.read_csv(
        RAW_DICTIONARY,
        usecols=["observed_term", "target", "source_text_field", "stratum", "status"],
    )
    lengths = df["observed_term"].map(word_count)
    df = df.assign(observed_term_word_count=lengths)

    by_target = {}
    for target, group in df.groupby("target", dropna=False):
        group_lengths = group["observed_term_word_count"]
        by_target[str(target)] = {
            "rows": int(len(group)),
            "word_length_counts": counter_to_dict(Counter(group_lengths)),
            "pct_1_2_words": pct(group_lengths <= 2),
            "pct_3_plus_words": pct(group_lengths >= 3),
        }

    by_source_text_field = {}
    for source_text_field, group in df.groupby("source_text_field", dropna=False):
        group_lengths = group["observed_term_word_count"]
        by_source_text_field[str(source_text_field)] = {
            "rows": int(len(group)),
            "word_length_counts": counter_to_dict(Counter(group_lengths)),
            "pct_1_2_words": pct(group_lengths <= 2),
            "pct_3_plus_words": pct(group_lengths >= 3),
        }

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": "T8c_observed_term_length_diagnostic",
        "rows": int(len(df)),
        "distinct_observed_terms": int(df["observed_term"].nunique()),
        "word_length_counts": counter_to_dict(Counter(lengths)),
        "pct_1_2_words": pct(lengths <= 2),
        "pct_3_plus_words": pct(lengths >= 3),
        "pct_5_plus_words": pct(lengths >= 5),
        "median_word_length": float(lengths.median()) if len(lengths) else 0.0,
        "mean_word_length": round(float(lengths.mean()), 2) if len(lengths) else 0.0,
        "by_target": by_target,
        "by_source_text_field": by_source_text_field,
        "diagnosis": "broad_short_ngram_extraction_supported",
        "updated_interpretation": (
            "The high distinct-term count is not caused by full text-segment extraction, "
            "but the artefact contains a substantial short n-gram component. The remaining "
            "issue is broad token/n-gram admission and weak canonical grouping."
        ),
        "lexical_layer_status": "provisional_pending_token_filtering_and_domain_grouping",
        "raw_values_emitted": False,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# T8c - Observed Term Length Diagnostic",
        "",
        "## Purpose",
        "",
        "This diagnostic tests whether the high volume in T8/T8b is caused by extracting multi-word phrases or complete text segments instead of lexical terms.",
        "",
        "The diagnostic reads the local-only working dictionary, computes word-count distributions over `observed_term`, and emits only aggregate counts. No raw source-derived terms are versioned.",
        "",
        "## Result",
        "",
        f"- Rows inspected: {summary['rows']}",
        f"- Distinct observed terms: {summary['distinct_observed_terms']}",
        f"- Word-length distribution: {summary['word_length_counts']}",
        f"- 1-2 word entries: {summary['pct_1_2_words']}%",
        f"- 3+ word entries: {summary['pct_3_plus_words']}%",
        f"- 5+ word entries: {summary['pct_5_plus_words']}%",
        f"- Median word length: {summary['median_word_length']}",
        f"- Mean word length: {summary['mean_word_length']}",
        "",
        "## Interpretation",
        "",
        "The full text-segment extraction hypothesis is not supported, but the short phrase/n-gram hypothesis is supported. The T8 artefact is not made of long copied segments; however, a substantial share of entries are 3-word observed terms.",
        "",
        "The remaining issue is therefore upstream token/n-gram admission and downstream semantic grouping: too many short lexical candidates are being admitted, and too few are being collapsed into canonical domain concepts.",
        "",
        "## Decision",
        "",
        "`LEXICAL_LAYER` remains provisional. T9 may freeze the other reference-layer objects, but this object should be marked `pending_rework` or `pending_token_filtering_and_domain_grouping` rather than accepted as a final seed dictionary.",
        "",
        "## Governance",
        "",
        "- No raw source-derived terms are emitted.",
        "- `source_text_field` and `stratum` remain mandatory for downstream rework.",
        "- `Symptom` remains candidate symptom-like lexical signal, not validated ground truth.",
    ]
    MEMO_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
