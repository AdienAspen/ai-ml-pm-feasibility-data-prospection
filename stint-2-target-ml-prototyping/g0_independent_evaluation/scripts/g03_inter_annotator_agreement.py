from __future__ import annotations

import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STINT2_ROOT = PROJECT_ROOT / "stint-2-target-ml-prototyping"
G0_ROOT = STINT2_ROOT / "g0_independent_evaluation"
PACKAGE_ROOT = G0_ROOT / "internal" / "g02_annotation_packages" / "by_target"
RESPONSE_ROOT = G0_ROOT / "internal" / "g02_annotation_responses"
OUT = G0_ROOT / "outputs" / "inter_annotator_agreement"
INTERNAL_OUT = G0_ROOT / "internal" / "g03_inter_annotator_agreement"

ANNOTATORS = {
    "chapter_team_annotator_01": {
        "label": "ANNOTATOR_1",
        "model": "Opus 5",
        "effort": "medium-effort",
        "temperature_grading_setup": "not_available_in_gui",
        "response_dir": RESPONSE_ROOT / "annotator_1",
    },
    "chapter_team_annotator_02": {
        "label": "ANNOTATOR_2",
        "model": "Gemini 3.6 Flash",
        "effort": "medium-effort",
        "temperature_grading_setup": "not_available_in_gui",
        "response_dir": RESPONSE_ROOT / "annotator_2",
    },
}

TARGETS = ["activity", "cause", "damage", "object_part", "symptom"]

CONTROLLED_VOCAB = {
    "Activity": {"activity_present", "condition_not_activity", "not_interpretable", "abstain"},
    "Cause": {"cause_present", "no_cause_stated", "not_interpretable", "abstain"},
    "Damage": {"damage_present", "symptom_not_damage", "action_not_damage", "not_interpretable", "abstain"},
    "Object Part": {"component_identified", "system_only", "no_component", "not_interpretable", "abstain"},
    "Symptom": {"observed_condition", "dispatch_motive", "ambiguous", "not_interpretable", "abstain"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str], mode_600: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    if mode_600:
        os.chmod(path, 0o600)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def target_name(slug: str) -> str:
    return {
        "activity": "Activity",
        "cause": "Cause",
        "damage": "Damage",
        "object_part": "Object Part",
        "symptom": "Symptom",
    }[slug]


def input_package_path(annotator: str, slug: str) -> Path:
    return PACKAGE_ROOT / f"g02_visible_package_{annotator}_{slug}.csv"


def response_path(annotator: str, slug: str) -> Path:
    response_dir = ANNOTATORS[annotator]["response_dir"]
    preferred = response_dir / f"g02_response_template_{annotator}_{slug}.csv"
    if preferred.exists():
        return preferred
    return PACKAGE_ROOT / f"g02_response_template_{annotator}_{slug}.csv"


def validate_one_file(annotator: str, slug: str) -> tuple[dict[str, object], list[dict[str, str]]]:
    target = target_name(slug)
    package_path = input_package_path(annotator, slug)
    response_file = response_path(annotator, slug)
    package_rows = read_csv(package_path) if package_path.exists() else []
    response_rows = read_csv(response_file) if response_file.exists() else []

    package_ids = [row.get("annotation_id", "").strip() for row in package_rows]
    response_ids = [row.get("annotation_id", "").strip() for row in response_rows]
    response_column = "annotator_response"
    if response_rows and response_column not in response_rows[0] and "response" in response_rows[0]:
        response_column = "response"
    response_counts = Counter(response_ids)
    duplicate_ids = sorted([key for key, count in response_counts.items() if key and count > 1])
    missing_ids = sorted(set(package_ids) - set(response_ids))
    extra_ids = sorted(set(response_ids) - set(package_ids))
    blank_ids = [idx + 1 for idx, value in enumerate(response_ids) if not value]

    allowed = CONTROLLED_VOCAB[target]
    invalid_values = sorted(
        {
            (row.get(response_column) or "").strip()
            for row in response_rows
            if (row.get(response_column) or "").strip()
            and (row.get(response_column) or "").strip() not in allowed
        }
    )
    nonempty_responses = sum(1 for row in response_rows if (row.get(response_column) or "").strip())
    blank_responses = len(response_rows) - nonempty_responses
    normalized_rows = []
    for row in response_rows:
        normalized = dict(row)
        normalized["annotator_response"] = (row.get(response_column) or "").strip()
        normalized.setdefault("annotator_notes", "")
        normalized.setdefault("annotator_id", annotator)
        normalized_rows.append(normalized)

    checks = {
        "file_exists": response_file.exists(),
        "row_parity": len(package_rows) == len(response_rows),
        "annotation_id_exact_set": not missing_ids and not extra_ids and not blank_ids,
        "annotation_id_unique": not duplicate_ids,
        "vocabulary_valid": not invalid_values,
        "all_rows_answered": blank_responses == 0,
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    report = {
        "annotator_id": annotator,
        "annotator_label": ANNOTATORS[annotator]["label"],
        "target": target,
        "input_rows": len(package_rows),
        "response_rows": len(response_rows),
        "nonempty_responses": nonempty_responses,
        "blank_responses": blank_responses,
        "missing_annotation_ids": len(missing_ids),
        "extra_annotation_ids": len(extra_ids),
        "duplicate_annotation_ids": len(duplicate_ids),
        "blank_annotation_ids": len(blank_ids),
        "invalid_vocab_values": len(invalid_values),
        "invalid_values_sample": ";".join(invalid_values[:10]),
        "response_column_used": response_column,
        "response_file": str(response_file.relative_to(STINT2_ROOT)),
        "status": status,
    }
    return report, normalized_rows


def load_manifest() -> dict[str, dict[str, str]]:
    path = G0_ROOT / "outputs" / "annotation_samples" / "g02_annotation_sample_manifest_sanitized.csv"
    return {row["annotation_id"]: row for row in read_csv(path)}


def load_visible_text_by_annotation_id() -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in sorted(PACKAGE_ROOT.glob("g02_visible_package_chapter_team_annotator_*.csv")):
        for row in read_csv(path):
            annotation_id = row.get("annotation_id", "").strip()
            text = row.get("text_pii_redacted", "").strip()
            if annotation_id and text:
                texts.setdefault(annotation_id, text)
    return texts


def percent(count: int, total: int) -> float:
    if not total:
        return 0.0
    return round((count / total) * 100, 4)


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    agree = sum(1 for a, b in pairs if a == b)
    labels = sorted({value for pair in pairs for value in pair})
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    expected = sum((left[label] / n) * (right[label] / n) for label in labels)
    observed = agree / n
    if math.isclose(1.0, expected):
        return None
    return round((observed - expected) / (1 - expected), 6)


def run_analysis(responses: dict[tuple[str, str], list[dict[str, str]]]) -> None:
    manifest = load_manifest()
    visible_text_by_id = load_visible_text_by_annotation_id()
    by_annotator_target: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    response_by_annotator: dict[str, dict[str, str]] = defaultdict(dict)

    for (annotator, slug), rows in responses.items():
        target = target_name(slug)
        for row in rows:
            annotation_id = row["annotation_id"].strip()
            response = row["annotator_response"].strip()
            by_annotator_target[(annotator, target)][response] += 1
            response_by_annotator[annotator][annotation_id] = response

    distribution_rows = []
    for (annotator, target), counts in sorted(by_annotator_target.items()):
        total = sum(counts.values())
        for label, count in sorted(counts.items()):
            distribution_rows.append(
                {
                    "annotator_id": annotator,
                    "annotator_label": ANNOTATORS[annotator]["label"],
                    "target": target,
                    "class_label": label,
                    "count": count,
                    "percent": percent(count, total),
                    "target_total": total,
                    "abstention_rate": percent(counts.get("abstain", 0), total),
                }
            )
    write_csv(
        OUT / "g03b_distribution_by_annotator_target_sanitized.csv",
        distribution_rows,
        [
            "annotator_id",
            "annotator_label",
            "target",
            "class_label",
            "count",
            "percent",
            "target_total",
            "abstention_rate",
        ],
    )

    overlap_ids = [
        annotation_id
        for annotation_id, row in manifest.items()
        if row.get("overlap_group") == "overlap"
        and annotation_id in response_by_annotator["chapter_team_annotator_01"]
        and annotation_id in response_by_annotator["chapter_team_annotator_02"]
    ]

    agreement_rows = []
    confusion_rows = []
    disagreement_rows = []
    groupings: dict[tuple[str, str], list[str]] = defaultdict(list)
    for annotation_id in overlap_ids:
        row = manifest[annotation_id]
        groupings[(row["target"], "ALL")].append(annotation_id)
        groupings[(row["target"], row["path_bucket"])].append(annotation_id)

    for (target, path_bucket), ids in sorted(groupings.items()):
        pairs = [
            (
                response_by_annotator["chapter_team_annotator_01"][annotation_id],
                response_by_annotator["chapter_team_annotator_02"][annotation_id],
            )
            for annotation_id in ids
        ]
        agree = sum(1 for a, b in pairs if a == b)
        agreement_rows.append(
            {
                "target": target,
                "path_bucket": path_bucket,
                "overlap_n": len(ids),
                "agreement_count": agree,
                "raw_agreement": round(agree / len(ids), 6) if ids else "",
                "cohen_kappa": cohen_kappa(pairs),
                "small_n_caveat": "YES" if len(ids) < 30 else "NO",
            }
        )
        for (left, right), count in sorted(Counter(pairs).items()):
            confusion_rows.append(
                {
                    "target": target,
                    "path_bucket": path_bucket,
                    "annotator_1_response": left,
                    "annotator_2_response": right,
                    "count": count,
                }
            )
        for annotation_id in ids:
            left = response_by_annotator["chapter_team_annotator_01"][annotation_id]
            right = response_by_annotator["chapter_team_annotator_02"][annotation_id]
            if left == right:
                continue
            disagreement_rows.append(
                {
                    "annotation_id": annotation_id,
                    "target": target,
                    "path_bucket": path_bucket,
                    "annotator_1_response": left,
                    "annotator_2_response": right,
                    "text_pii_redacted": visible_text_by_id.get(annotation_id, ""),
                }
            )

    write_csv(
        OUT / "g03c_inter_annotator_agreement_sanitized.csv",
        agreement_rows,
        ["target", "path_bucket", "overlap_n", "agreement_count", "raw_agreement", "cohen_kappa", "small_n_caveat"],
    )
    write_csv(
        OUT / "g03c_confusion_matrices_sanitized.csv",
        confusion_rows,
        ["target", "path_bucket", "annotator_1_response", "annotator_2_response", "count"],
    )

    sample_rows = []
    by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in disagreement_rows:
        if row["path_bucket"] == "ALL":
            by_target[row["target"]].append(row)
    for target in sorted(by_target):
        sample_rows.extend(sorted(by_target[target], key=lambda row: (row["path_bucket"], row["annotation_id"]))[:6])
    sample_rows = sample_rows[:30]
    write_csv(
        INTERNAL_OUT / "g03d_disagreement_review_sample_internal.csv",
        sample_rows,
        [
            "annotation_id",
            "target",
            "path_bucket",
            "annotator_1_response",
            "annotator_2_response",
            "text_pii_redacted",
        ],
        mode_600=True,
    )
    write_csv(
        OUT / "g03d_disagreement_review_sample_manifest_sanitized.csv",
        [
            {
                "annotation_id": row["annotation_id"],
                "target": row["target"],
                "path_bucket": row["path_bucket"],
                "annotator_1_response": row["annotator_1_response"],
                "annotator_2_response": row["annotator_2_response"],
                "text_in_versioned_artifact": "False",
            }
            for row in sample_rows
        ],
        [
            "annotation_id",
            "target",
            "path_bucket",
            "annotator_1_response",
            "annotator_2_response",
            "text_in_versioned_artifact",
        ],
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    INTERNAL_OUT.mkdir(parents=True, exist_ok=True)
    os.chmod(INTERNAL_OUT, 0o700)

    validation_rows = []
    responses: dict[tuple[str, str], list[dict[str, str]]] = {}
    for annotator in ANNOTATORS:
        for slug in TARGETS:
            report, rows = validate_one_file(annotator, slug)
            validation_rows.append(report)
            responses[(annotator, slug)] = rows

    write_csv(
        OUT / "g03a_structural_validation_sanitized.csv",
        validation_rows,
        [
            "annotator_id",
            "annotator_label",
            "target",
            "input_rows",
            "response_rows",
            "nonempty_responses",
            "blank_responses",
            "missing_annotation_ids",
            "extra_annotation_ids",
            "duplicate_annotation_ids",
            "blank_annotation_ids",
            "invalid_vocab_values",
            "invalid_values_sample",
            "response_column_used",
            "response_file",
            "status",
        ],
    )

    pass_count = sum(1 for row in validation_rows if row["status"] == "PASS")
    summary = {
        "task": "G0.3_inter_annotator_agreement",
        "created_at_utc": utc_now(),
        "annotator_metadata": {
            annotator: {
                key: str(value) if isinstance(value, Path) else value
                for key, value in metadata.items()
            }
            for annotator, metadata in ANNOTATORS.items()
        },
        "structural_validation_status": "PASS" if pass_count == len(validation_rows) else "FAIL",
        "files_expected": len(validation_rows),
        "files_passed": pass_count,
        "files_failed": len(validation_rows) - pass_count,
        "analysis_outputs_emitted": pass_count == len(validation_rows),
        "blocking_rule": "If one response file fails structural validation, the full file is rejected and agreement is not computed.",
    }
    write_json(OUT / "g03_summary_sanitized.json", summary)

    if pass_count != len(validation_rows):
        return

    run_analysis(responses)


if __name__ == "__main__":
    main()
