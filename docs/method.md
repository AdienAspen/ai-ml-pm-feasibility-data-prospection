# Method and pipeline

## 1. Define the decision before modeling

For each target, specify the source path, counting unit, registration level, candidate catalog type, and claim to be tested. A direct field, an asset join, a text anchor, an enabled code, and a correct assignment are different outcomes. The next stage is attempted only when its inputs and denominator are valid.

## 2. Reconstruct evidence

Relational orders and daily snapshots remain separate. Source rows are linked to physical records or provisional events with explicit keys. Duplicate surface text can appear in many records, so vocabulary coverage and evaluation must preserve both the record unit and the text-equivalence unit. Missing rows are declared, never silently counted as zero.

## 3. Build vocabularies with provenance

The corpus-derived route uses a **model-eligible construction universe** that excludes independent evaluation material and text-equivalent duplicates. A full-corpus view is retained for descriptive statistics. Label-bearing snippets are masked before extraction. The process normalizes text, extracts neutral one-to-three-token forms, filters by path, embeds the surviving forms, and clusters their vectors. Target assignment is deferred until the concepts can be inspected; catalog mapping is a later and separate artifact.

The external-reference route transcribes domain terms from frozen, non-client sources. A term from that route is marked as reference evidence, not learned from held-out text. Every concept retains its construction method and source. A concept may map to zero, one, or several destination codes; an absent mapping remains an explicit candidate gap rather than a verified catalog defect.

The semantic representation used `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. `MiniBatchKMeans` grouped normalized embeddings in the corpus-derived route. Cosine similarity compared text and semantic prototypes. MiniLM is an embedding model; clustering and similarity are separate operations.

## 4. Resolve the destination space

The investigated chain was:

```text
detected concept → candidate hierarchy node → inherited profile
                 → enabled catalog group → reachable code
```

Node matching is site-aware because object numbering can repeat across installations. Profile inheritance uses the nearest valid ancestor; a missing profile remains `no_profile_no_filter`, not a fabricated profile. An ambiguous node can still yield a profile when its candidates share the same profile. A profile produces permitted **groups**, then the catalog expands those groups to **codes**. Code reachability is not code correctness.

Material-item descriptions provide another signal, distinct from the order narrative. Comparisons between that crosswalk and narrative-based component resolution are diagnostic. If an Object Part signal helped resolve a node, that same node's profile-filtered code space cannot independently validate the signal.

## 5. Evaluate and report

Freeze prototype construction, thresholds, and split rules before consulting a held-out set. Keep development and diagnostic-calibration material distinct from final evaluation. Report precision with coverage and abstention; report macro F1 alongside weighted F1. Every metric names its evaluation-set type, sample size, path, and threshold. Compare methods on the same eligible universe, with exclusions stated separately.

The reusable [signal report template](../templates/signal_report_template.md) turns presence, consistency, discrimination, expressibility, and dependency into a decision with stated conditions.
