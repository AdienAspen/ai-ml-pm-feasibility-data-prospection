# Evidence and evaluation

## Evidence register

Each figure is identified by `target × path × level × metric_id`, with a declared counting unit, eligible universe, source, evidence level, and limitation. Metric IDs use a controlled vocabulary so a reconciliation can compare figures one by one. Observed fields, validated labels, structural matches, proxy anchors, and analyst-derived diagnostics must not be relabeled as one another.

The key distinction is between **information present in a record** and **classification into the correct destination code**. A semantic anchor can support the first claim. It does not prove the second. Likewise, a code enabled by a technical-object profile is only a legal candidate.

## Independent diagnostic annotation

Blind packages showed annotators the redacted text and an annotation ID, without model proposals, path, stratum, score, anchor source, or tier. Two LLM model families annotated overlapping subsets. Their responses were kept separate; disagreements were registered instead of averaged into a consensus label. These are diagnostic labels, not human domain-expert adjudications.

The response record tracks evaluation independence, label-generation method, annotator identity, protocol version, excluded mechanisms, and evaluation role. A response created after seeing a pipeline proposal is `human_validated` or otherwise proposal-informed, never `independent`. Diagnostic calibration material is explicitly ineligible for final held-out claims.

Agreement is reported as raw agreement, Cohen's κ, confusion matrix, and agreement by class; Gwet's AC1 is included where prevalence makes κ hard to interpret. Presence-level and group/code-level agreement are separate questions. The shared subset is reported per path when available, with small cells identified as imprecise.

## Leakage and split controls

- Exclude evaluation units, and duplicate text-equivalence classes that contain them, from vocabulary construction and model fitting.
- Mask explicit target assignments in source text before extraction or scoring.
- Keep the training-exclusion count and overlap check as programmatic assertions.
- Select thresholds only on the calibration split; a held-out result cannot choose its own threshold.
- Treat any blind diagnostic sample used to improve vocabulary or prototypes as construction data and exclude it from later independent evaluation.

Any later protocol revision gets its own registration. Earlier versions remain interpretable under the definitions that generated their labels.
