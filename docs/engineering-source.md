# Engineering source in this study edition

This repository preserves selected engineering files from successive study stages. It is a reviewable account of the method, not a replay package for the original data. Source-dependent scripts name their expected inputs and outputs, but those inputs and generated artifacts are outside this edition.

## Stage map

| Stage | Included engineering | Purpose |
|---|---|---|
| Initial prospection | [`src/asset_ml_feasibility`](../src/asset_ml_feasibility) and [`scripts`](../scripts) | Inventory, schema and structural scans, catalog recognition, and evidence pair classification |
| Reference construction | [`stint-1.1-reference-layer`](../stint-1.1-reference-layer) | Reference provenance, source acceptance, and term-length diagnostics |
| Evidence reconstruction | [`stint-1-evidence-ground-truth`](../stint-1-evidence-ground-truth) | Lexical readiness, concept identity checks, denominator rules, and evidence lineage |
| Target prototyping | [`stint-2-target-ml-prototyping`](../stint-2-target-ml-prototyping) | Independent evaluation policy, agreement analysis, conservative term filtering, and response validation |
| Public method adaptations | [`study_methods`](../study_methods) | Semantic grouping, candidate crosswalk, and profile scoping without operational vocabulary or configuration |

The original stage names are retained to show the order in which evidence and modeling questions were addressed. The public `main` branch is a new, reviewed history rather than a fork of the restricted operational history.

## Method sequence

1. Inventory source families and inspect structures before using their text.
2. Register provenance, tier, physical counting unit, and destination constraints separately.
3. Form denominators by target and source path. A missing or zero denominator is declared.
4. Build a corpus-native vocabulary only from model-eligible text. Keep reference terms and destination codes in separate artifacts.
5. Encode eligible terms with MiniLM, compare candidate MiniBatchKMeans groupings using cosine silhouette, and check concentration before naming concepts.
6. Map concepts to zero or more destination codes. Resolve hierarchy profiles and expand allowed groups to codes as distinct operations.
7. Validate independent annotation packages and report agreement, prevalence, coverage, and abstention with their units and limitations.

## Publication adaptations

The public edition removes original records, generated vocabularies, catalog contents, hierarchy nodes, annotation responses, and source-specific configuration. Files that required change are intentionally adapted:

| File or area | Adaptation |
|---|---|
| `schema_profile.py` and `catalog_loader.py` | Generic asset and catalog hints replace source-specific identifiers. |
| `g20c_step2_filtering.py` | A library stopword set replaces the corpus-derived boilerplate list; restricted entity terms must be supplied in the controlled environment. |
| `g03_inter_annotator_agreement.py` | Repository root is derived from the script location. |
| `g20ef_validate_responses.py` | Response validation reads the supplied catalog list without hard-coded original cardinalities. |
| `study_methods/` | Data-free adaptations of semantic grouping, crosswalk scoring, and profile-chain logic; no original synonym list, profile, or code values are embedded. |
| Policy documents | Source-specific examples and exact operational figures are removed while retaining the decision rules. |

These adaptations are disclosed because their outputs must not be treated as a reproduction of the original study. In particular, the public term filter will differ from the controlled run, and the semantic grouping adaptation stops if no candidate passes its concentration gate.

## Input and output boundary

The source-dependent scripts expect controlled inputs in their named `data/`, `reference_layer/`, or stage `outputs/` locations. No such inputs are provided here. Put only data you have rights to use into a separate controlled environment; do not commit operational records, derived term lists, visible annotation packages, model weights, or response files to this repository.

The published policies and [`docs/method.md`](method.md) explain the decisions even when a script cannot be run against the original inputs.
