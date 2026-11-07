"""Data-free adaptation of material-description to catalog candidate scoring.

The original crosswalk used a controlled synonym list that is not distributed.
This public method takes a caller-supplied normalizer and never emits a label of
verified correctness. Candidate lists may contain zero, one, or many codes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class CatalogEntry:
    group: str
    code: str
    description: str


@dataclass(frozen=True)
class Candidate:
    group: str
    code: str
    score: float
    tier: str
    evidence_type: str = "expert_inference"


def basic_tokens(value: str) -> list[str]:
    """Basic lexical form; a controlled run may supply another normalizer."""
    return [part for part in re.sub(r"[^a-z0-9]+", " ", value.lower()).split() if len(part) > 1]


def score_candidate(
    material_description: str,
    catalog_description: str,
    normalizer: Callable[[str], list[str]] = basic_tokens,
) -> float:
    material = set(normalizer(material_description))
    catalog = set(normalizer(catalog_description))
    if not material or not catalog:
        return 0.0
    score = len(material & catalog) / len(catalog)
    head = normalizer(material_description)[:1]
    if head and head[0] in catalog:
        score += 0.35
    if catalog <= material:
        score += 0.25
    return round(min(score, 1.0), 6)


def tier(score: float) -> str:
    if score >= 0.85:
        return "strong"
    if score >= 0.55:
        return "medium"
    if score > 0:
        return "weak"
    return "no_candidate"


def candidate_codes(
    material_description: str,
    catalog: Iterable[CatalogEntry],
    normalizer: Callable[[str], list[str]] = basic_tokens,
) -> list[Candidate]:
    results = []
    for entry in catalog:
        score = score_candidate(material_description, entry.description, normalizer)
        if score > 0:
            results.append(Candidate(entry.group, entry.code, score, tier(score)))
    return sorted(results, key=lambda item: (-item.score, item.group, item.code))
