from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_ROOT = PROJECT_ROOT / "stint-1.1-reference-layer"
STINT_ROOT = PROJECT_ROOT / "stint-1-evidence-ground-truth"
F1_ROOT = STINT_ROOT / "phase_1_lexical"
OUTPUTS_DIR = F1_ROOT / "outputs"
GROUPED_DIR = OUTPUTS_DIR / "lexical_layer_v2"

RAW_LEXICAL_V1 = (
    REFERENCE_ROOT
    / "reference_layer"
    / "lexical_layer"
    / "lexical_seed_dictionary_v1.csv"
)
LEXICAL_V2 = GROUPED_DIR / "lexical_layer_v2_sanitized.csv"
CANONICAL_VOCAB_WORKING = OUTPUTS_DIR / "canonical_vocabulary" / "canonical_vocabulary_v1_working.csv"
EXTERNAL_FAILURE_VOCAB = OUTPUTS_DIR / "canonical_vocabulary" / "external_failure_vocabulary_v1.csv"
TRANSLATION_ALIASES_ES = OUTPUTS_DIR / "canonical_vocabulary" / "translation_aliases_es_v1.csv"

MODEL_NAME = os.environ.get(
    "F1D2_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

TARGET_THRESHOLDS = {
    "Symptom": 0.48,
    "Object Part": 0.52,
    "Damage": 0.48,
    "Cause": 0.48,
    "Activity": 0.52,
    "FLOC leaf": 0.52,
    "Activity Type": 0.52,
    "unknown": 0.56,
}


# Public adaptation: the controlled abbreviation map is not distributed.
ABBREVIATIONS = {}


def stable_key(value: object, prefix: str) -> str:
    raw = "" if value is None or pd.isna(value) else str(value)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).lower()
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    tokens = []
    for token in text.split():
        token = ABBREVIATIONS.get(token.strip(), token.strip())
        if token:
            tokens.append(token)
    return " ".join(tokens)


def consolidate_term(term: object) -> str:
    tokens = normalize_text(term).split()
    collapsed: list[str] = []
    for token in tokens:
        if not collapsed or collapsed[-1] != token:
            collapsed.append(token)
    return " ".join(collapsed)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_observed_terms() -> dict[str, str]:
    if not RAW_LEXICAL_V1.exists():
        raise FileNotFoundError(f"Missing raw lexical working input: {RAW_LEXICAL_V1}")
    raw = pd.read_csv(RAW_LEXICAL_V1)
    raw["consolidated_term"] = raw["observed_term"].map(consolidate_term)
    raw["term_key"] = raw["consolidated_term"].map(lambda value: stable_key(value, "TERM"))
    lookup: dict[str, str] = {}
    for term_key, group in raw.groupby("term_key"):
        values = sorted(set(str(v) for v in group["consolidated_term"].dropna() if str(v).strip()))
        if values:
            lookup[term_key] = values[0]
    return lookup


def load_vocabulary() -> pd.DataFrame:
    frames = []
    if CANONICAL_VOCAB_WORKING.exists():
        frames.append(pd.read_csv(CANONICAL_VOCAB_WORKING))
    if EXTERNAL_FAILURE_VOCAB.exists():
        frames.append(pd.read_csv(EXTERNAL_FAILURE_VOCAB))
    if not frames:
        raise FileNotFoundError("Missing vocabulary inputs.")
    vocab = pd.concat(frames, ignore_index=True, sort=False)
    vocab = vocab[vocab["canonical_concept"].notna()].copy()
    vocab["match_text"] = vocab["canonical_concept"]
    vocab["match_text_source"] = "canonical_concept"
    if TRANSLATION_ALIASES_ES.exists():
        aliases = pd.read_csv(TRANSLATION_ALIASES_ES)
        alias_rows = []
        for _, alias in aliases.iterrows():
            alias_rows.append(
                {
                    "concept_id": alias.get("canonical_concept_id", ""),
                    "canonical_concept_key": alias.get("canonical_concept_key", ""),
                    "canonical_concept": alias.get("canonical_alias_es", ""),
                    "target": alias.get("target", ""),
                    "namespace": alias.get("namespace", ""),
                    "target_field": alias.get("target_field", ""),
                    "vocabulary_owner": alias.get("vocabulary_owner", ""),
                    "subsystem": alias.get("subsystem", ""),
                    "semantic_level": alias.get("semantic_level", ""),
                    "tier": alias.get("tier", "silver-medium"),
                    "evidence_type": alias.get("evidence_type", "expert_inference"),
                    "match_text": alias.get("canonical_alias_es", ""),
                    "match_text_source": "translation_alias_es",
                }
            )
        if alias_rows:
            vocab = pd.concat([vocab, pd.DataFrame(alias_rows)], ignore_index=True, sort=False)
    vocab["canonical_concept_norm"] = vocab["canonical_concept"].map(normalize_text)
    vocab = vocab[vocab["canonical_concept_norm"].astype(bool)].copy()
    return vocab.reset_index(drop=True)


def allowed_targets(observed_target: str) -> set[str]:
    if observed_target and observed_target != "unknown":
        return {observed_target}
    return {"Symptom", "Object Part", "Damage", "Cause", "Activity", "FLOC leaf", "Activity Type"}


def semantic_status(score: float, threshold: float) -> str:
    if score >= max(0.7, threshold + 0.12):
        return "semantic_anchor_high"
    return "semantic_anchor_candidate"


def main() -> None:
    if not LEXICAL_V2.exists():
        raise FileNotFoundError(f"Missing lexical input: {LEXICAL_V2}")
    term_lookup = load_observed_terms()
    lexical = pd.read_csv(LEXICAL_V2)
    vocab = load_vocabulary()

    model = SentenceTransformer(MODEL_NAME)

    vocab_texts = vocab["canonical_concept_norm"].tolist()
    vocab_embeddings = model.encode(vocab_texts, normalize_embeddings=True, show_progress_bar=False)
    vocab_embeddings = np.asarray(vocab_embeddings, dtype=np.float32)

    term_texts = [term_lookup.get(str(row.get("term_key", "")), "") for _, row in lexical.iterrows()]
    term_embeddings = model.encode(term_texts, normalize_embeddings=True, show_progress_bar=False)
    term_embeddings = np.asarray(term_embeddings, dtype=np.float32)

    rows: list[dict] = []
    vocab_targets = vocab["target"].fillna("").astype(str).tolist()

    for idx, (_, lex) in enumerate(lexical.iterrows()):
        observed_target = str(lex.get("target", "") or "unknown")
        targets = allowed_targets(observed_target)
        candidate_idx = [i for i, target in enumerate(vocab_targets) if target in targets]
        if not candidate_idx or not term_texts[idx]:
            best_score = 0.0
            best = None
        else:
            matrix = vocab_embeddings[candidate_idx]
            scores = matrix @ term_embeddings[idx]
            local_best = int(np.argmax(scores))
            best_score = float(scores[local_best])
            best = vocab.iloc[candidate_idx[local_best]]

        threshold = TARGET_THRESHOLDS.get(observed_target, TARGET_THRESHOLDS["unknown"])
        mapped = bool(best is not None and best_score >= threshold)
        if mapped:
            canonical_concept_id = best.get("concept_id", "")
            canonical_concept_key = best.get("canonical_concept_key", "")
            target = best.get("target", observed_target)
            owner = best.get("vocabulary_owner", "")
            subsystem = best.get("subsystem", "")
            semantic_level = best.get("semantic_level", "")
            source_tier = best.get("tier", "")
            match_text_source = best.get("match_text_source", "canonical_concept")
            status = semantic_status(best_score, threshold)
            tier = "silver-medium" if source_tier in {"gold", "silver-high", "silver-medium"} else "silver-medium"
            evidence_type = "expert_inference"
        else:
            canonical_concept_id = ""
            canonical_concept_key = ""
            target = observed_target
            owner = ""
            subsystem = ""
            semantic_level = ""
            match_text_source = ""
            status = "unresolved"
            tier = "unresolved"
            evidence_type = "unresolved"

        rows.append(
            {
                "term_key": lex.get("term_key"),
                "source_concept_id": lex.get("concept_id"),
                "target": target,
                "observed_target_hint": observed_target,
                "source_text_field": lex.get("source_text_field"),
                "stratum": lex.get("stratum"),
                "contractor_path": lex.get("contractor_path"),
                "record_count": int(lex.get("record_count", 0) or 0),
                "mapped_to_canonical_concept": mapped,
                "canonical_concept_id": canonical_concept_id,
                "canonical_concept_key": canonical_concept_key,
                "vocabulary_owner": owner,
                "subsystem": subsystem,
                "semantic_level": semantic_level,
                "match_score": round(best_score, 4),
                "match_method": "multilingual_embedding_cosine" if mapped else "below_threshold",
                "match_text_source": match_text_source,
                "match_threshold": threshold,
                "embedding_model": MODEL_NAME,
                "evidence_type": evidence_type,
                "tier": tier,
                "status": status,
                "label_generation_method": "semantic_embedding_plus_translation_alias_rule_set_v1",
                "evaluation_independence": "derived_from_rules",
                "can_support_contractual_denominator": False,
                "can_support_proxy_denominator": mapped,
                "raw_values_emitted": False,
            }
        )

    fields = [
        "term_key",
        "source_concept_id",
        "target",
        "observed_target_hint",
        "source_text_field",
        "stratum",
        "contractor_path",
        "record_count",
        "mapped_to_canonical_concept",
        "canonical_concept_id",
        "canonical_concept_key",
        "vocabulary_owner",
        "subsystem",
        "semantic_level",
        "match_score",
        "match_method",
        "match_text_source",
        "match_threshold",
        "embedding_model",
        "evidence_type",
        "tier",
        "status",
        "label_generation_method",
        "evaluation_independence",
        "can_support_contractual_denominator",
        "can_support_proxy_denominator",
        "raw_values_emitted",
    ]
    output = GROUPED_DIR / "lexical_semantic_domain_grouping_with_aliases_v1_sanitized.csv"
    write_csv(output, rows, fields)

    result_df = pd.DataFrame(rows)
    mapped_df = result_df[result_df["mapped_to_canonical_concept"] == True]
    target_summary = {}
    for target, group in result_df.groupby("observed_target_hint", dropna=False):
        mapped_group = group[group["mapped_to_canonical_concept"] == True]
        target_summary[str(target)] = {
            "rows": int(len(group)),
            "mapped_rows": int(len(mapped_group)),
            "unresolved_rows": int(len(group) - len(mapped_group)),
            "mapped_pct": round(100 * len(mapped_group) / len(group), 2) if len(group) else 0.0,
            "distinct_canonical_concepts": int(mapped_group["canonical_concept_id"].nunique()),
        }

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": "F1d4_semantic_grouping_with_translation_aliases",
        "embedding_model": MODEL_NAME,
        "input_rows": int(len(result_df)),
        "mapped_rows": int(len(mapped_df)),
        "unresolved_rows": int(len(result_df) - len(mapped_df)),
        "mapped_pct": round(100 * len(mapped_df) / len(result_df), 2) if len(result_df) else 0.0,
        "distinct_term_keys": int(result_df["term_key"].nunique()),
        "distinct_canonical_concepts_mapped": int(mapped_df["canonical_concept_id"].nunique()),
        "target_summary": target_summary,
        "vocabulary_owner_counts_mapped": {
            str(k): int(v) for k, v in mapped_df["vocabulary_owner"].value_counts(dropna=False).sort_index().items()
        },
        "status_counts": {
            str(k): int(v) for k, v in result_df["status"].value_counts(dropna=False).sort_index().items()
        },
        "match_text_source_counts": {
            str(k): int(v)
            for k, v in mapped_df["match_text_source"].value_counts(dropna=False).sort_index().items()
        },
        "thresholds": TARGET_THRESHOLDS,
        "observed_to_concept_mapping_performed": True,
        "translation_alias_layer_used": TRANSLATION_ALIASES_ES.exists(),
        "label_generation_method": "semantic_embedding_plus_translation_alias_rule_set_v1",
        "evaluation_independence": "derived_from_rules",
        "raw_values_emitted": False,
        "outputs": {
            "grouping_csv": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/lexical_layer_v2/lexical_semantic_domain_grouping_with_aliases_v1_sanitized.csv",
            "summary_json": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1d4_semantic_grouping_with_aliases_summary.json",
            "memo": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1d4_semantic_grouping_with_aliases_memo.md",
        },
    }
    (OUTPUTS_DIR / "f1d4_semantic_grouping_with_aliases_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    lines = [
        "# F1d4 - Semantic Grouping With Translation Aliases",
        "",
        "## Purpose",
        "",
        "This pass uses multilingual sentence embeddings to anchor observed lexical term keys to canonical concepts and Spanish translation aliases.",
        "",
        "It emits only keys, IDs, scores, and aggregate metadata. It does not emit observed terms or canonical concept text.",
        "",
        "## Result",
        "",
        f"- Embedding model: `{MODEL_NAME}`",
        f"- Input rows: {summary['input_rows']}",
        f"- Mapped rows: {summary['mapped_rows']}",
        f"- Unresolved rows: {summary['unresolved_rows']}",
        f"- Mapped percentage: {summary['mapped_pct']}%",
        f"- Distinct canonical concepts mapped: {summary['distinct_canonical_concepts_mapped']}",
        "",
        "## Target Summary",
        "",
        "| target | rows | mapped_rows | unresolved_rows | mapped_pct | distinct_canonical_concepts |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for target, stats in sorted(target_summary.items()):
        lines.append(
            f"| {target} | {stats['rows']} | {stats['mapped_rows']} | {stats['unresolved_rows']} | {stats['mapped_pct']} | {stats['distinct_canonical_concepts']} |"
        )
    lines.extend(
        [
            "",
            "## Governance",
            "",
            "- Semantic matches are `expert_inference`, not `validated_mapping`.",
            "- All labels remain `derived_from_rules`; they cannot evaluate the same rule set in STINT_2.",
            "- `unresolved` remains an expected and valid output.",
        "- Translation alias layer was used, but aliases remain `expert_inference` and preserve the original canonical concept ID.",
        ]
    )
    (OUTPUTS_DIR / "f1d4_semantic_grouping_with_aliases_memo.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "task": summary["task"],
                "mapped_rows": summary["mapped_rows"],
                "unresolved_rows": summary["unresolved_rows"],
                "mapped_pct": summary["mapped_pct"],
                "distinct_canonical_concepts_mapped": summary["distinct_canonical_concepts_mapped"],
                "raw_values_emitted": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
