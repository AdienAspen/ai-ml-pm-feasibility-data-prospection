"""Public adaptation of the corpus-native semantic grouping step.

The study built concepts from eligible text before assigning targets or mapping
to destination codes. This module retains that ordering and the clustering
selection rule. It contains no corpus vocabulary or operational examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score


MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class GroupingConfig:
    candidate_counts: tuple[int, ...]
    random_state: int = 17
    sample_size: int = 3000
    max_cluster_share: float = 0.30


def encode_terms(terms: Iterable[str], model_id: str = MODEL_ID) -> np.ndarray:
    """MiniLM encodes text; clustering and similarity are separate operations."""
    values = list(terms)
    if not values or any(not value.strip() for value in values):
        raise ValueError("Terms must be nonempty")
    vectors = SentenceTransformer(model_id).encode(
        values,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def select_grouping(vectors: np.ndarray, config: GroupingConfig) -> tuple[np.ndarray, list[dict]]:
    """Select by cosine silhouette among candidates passing concentration gate."""
    if vectors.ndim != 2 or len(vectors) < 3:
        raise ValueError("At least three embedding rows are required")
    if not config.candidate_counts:
        raise ValueError("At least one candidate cluster count is required")
    rng = np.random.default_rng(config.random_state)
    sample = np.sort(
        rng.choice(len(vectors), min(config.sample_size, len(vectors)), replace=False)
    )
    rows: list[dict] = []
    selected_labels: np.ndarray | None = None
    selected_score = -np.inf
    for count in config.candidate_counts:
        if count < 2 or count >= len(vectors):
            raise ValueError("Each cluster count must be between 2 and n-1")
        model = MiniBatchKMeans(
            n_clusters=count,
            random_state=config.random_state,
            batch_size=2048,
            n_init=3,
            max_iter=100,
            reassignment_ratio=0.01,
        )
        labels = model.fit_predict(vectors)
        sampled_labels = labels[sample]
        if len(set(sampled_labels)) < 2 or len(set(sampled_labels)) >= len(sample):
            score = float("nan")
        else:
            score = float(silhouette_score(vectors[sample], sampled_labels, metric="cosine"))
        largest_share = float(np.bincount(labels, minlength=count).max() / len(labels))
        passes = largest_share <= config.max_cluster_share
        rows.append(
            {
                "candidate_clusters": count,
                "cosine_silhouette": score,
                "largest_cluster_share": largest_share,
                "concentration_gate_pass": passes,
            }
        )
        if passes and np.isfinite(score) and score > selected_score:
            selected_labels = labels
            selected_score = score
    if selected_labels is None:
        raise RuntimeError("No clustering candidate passed the concentration gate")
    return selected_labels, rows


def assert_construction_excludes_evaluation(
    construction_keys: Iterable[str], evaluation_keys: Iterable[str]
) -> None:
    """Block transductive vocabulary construction from evaluation records."""
    overlap = set(construction_keys) & set(evaluation_keys)
    if overlap:
        raise ValueError(f"Construction/evaluation overlap: {len(overlap)} units")
