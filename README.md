# Plant Maintenance Catalog Mapping — ML Feasibility Study

This industry-grade POC studies when legacy plant maintenance records contain enough evidence to support mapping into SAP S/4HANA Plant Maintenance catalog codes, and what must be decided or prepared before modeling is justified.

This is a **study repository**: its deliverable is an inspectable method, decision framework, and set of reviewed findings. It is not a production service or a deployed classifier. No supervised classifier is trained or shipped here, and no result establishes contractual accuracy.

## Development stages

The study followed successive development stages, called **stints**. Initial source prospection established the units and paths; the reference stage froze vocabulary and canonical constraints; evidence reconstruction established path-specific denominators; target-specific prototyping then tested text signal, catalog expressibility, and component resolution. The original operational branches preserve that development history in a restricted repository. This public repository presents the reviewed method in one clean `main` history.

## Scope and findings

The central problem is carrying technicians' open language into a controlled catalog without confusing **signal in the text**, **codes enabled for the technical object**, and **correct code assignment**. Those are three different claims. A repeatable text signal may have no permitted destination code; a permitted code may still be wrong for the record.

The study found that direct fields and structural joins can settle some decisions without a model. Text-based decisions require a valid counting unit, independent evaluation, and a catalog configuration that can express the result. Daily snapshots need episode reconstruction before they represent completed maintenance histories. The [engineering findings](docs/engineering-findings.md) explain these boundaries and the remaining decisions.

| Decision layer | What it establishes | What remains to check |
|---|---|---|
| Deterministic structure | Direct fields and asset-level joins | Field and hierarchy validity |
| Text-addressable signal | Domain concepts detected in narrative text | Independent precision and class discrimination |
| Operator decision | Registration level and permitted code space | Catalog/profile configuration |
| Data preparation | Snapshot-to-episode reconstruction | Episode boundaries and completion evidence |

Figures in the operational study were recorded with a unit, universe, source, evidence level, and limitation. This account emphasizes those relationships. See [evidence and evaluation](docs/evidence-and-evaluation.md).

## Signal Report Template

A reusable decision instrument for feasibility studies that map free text into a controlled vocabulary. It scores each decision unit on five dimensions and assigns a verdict: Ready · Conditional · Not ready · Not assessable.

→ [Template](templates/signal_report_template.md) · [Blank scorecard (CSV)](templates/signal_report_template.csv)

## Sources and targets

The study handled three source shapes separately. Their counting units were never added across paths.

| Source shape | Working unit | Necessary qualification |
|---|---|---|
| Relational maintenance records | Work order or explicitly named source unit | Structured fields and narrative text have different evidentiary roles |
| Daily PDF snapshots | Snapshot row or estimated event | Multiple rows may describe one maintenance episode |
| Daily workbooks | Snapshot row or estimated event | Repeated daily entries require temporal consolidation |

The [source card](docs/source-card.md) describes field categories, scale, and quality conditions without reproducing operational records. Illustrative examples are created for this publication and contain no operational records.

| Target | Destination or field | Resolution investigated |
|---|---|---|
| Material and activity type | Direct structured field | Observed value |
| Functional location | Technical-object hierarchy | Structural asset join; component-level claims require more evidence |
| Symptom | Catalog S | Domain signal and profile-scoped code space |
| Object part | Catalog B | Narrative concepts, material crosswalk, and component/profile constraints |
| Damage | Catalog C | Physical-process signal and group/code annotation |
| Cause | Catalog 5 | Causal signal and profile-scoped code space |
| Activity | Catalog A | Work described versus code applicability |

A catalog profile restricts the valid group-and-code pairs at a chosen registration level. Detecting a concept, finding an enabled code, and validating that code are separate steps.

## Method and evidence

```text
source record → normalized text / direct fields → domain concept
              → hierarchy candidate → inherited catalog profile
              → eligible group + code pair → independent check
```

Not every target uses every stage. Direct fields are read as observed values; asset-level joins are structural; text-derived concepts and code candidates remain conditional until evaluated. The [method specification](docs/method.md) describes the stages, controls, and decision points.

| Stage | Purpose | Main output |
|---|---|---|
| Source prospection | Identify fields, paths, units, and quality limits | Source inventory and path definitions |
| Reference construction | Freeze canonical constraints and external vocabularies | Versioned reference inputs |
| Evidence reconstruction | Reconcile source rows to target-specific denominators | Path-specific evidence register |
| Independent evaluation | Separate annotation from candidate-generation mechanisms | Annotator-specific response sets and agreement diagnostics |
| Target-specific prototyping | Test domain detection, catalog coverage, and hierarchy resolution | Diagnostic signal and gap partitions |

Filtered corpus terms were embedded with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Normalized vectors were grouped using `MiniBatchKMeans`; target assignment and catalog mapping happened later as separate steps. Cosine similarity compared embedded texts and prototypes. MiniLM creates the vectors; it is not itself the clustering algorithm. The [method specification](docs/method.md) distinguishes the corpus-derived vocabulary from external reference vocabulary and the destination catalog.

The evidence register kept proxy, inferred, observed, and validated claims distinct. A count of reachable candidates is never presented as verified code accuracy.

## Annotation and evaluation

Two LLM model families performed blind **diagnostic** annotation. They were independent of the candidate pipeline at the instance level, but they were not human subject-matter experts. Responses remained separate; disagreements were measured rather than silently reconciled. Protocol version, sampling design, overlap, label-generation method, and exclusions qualify each metric.

Agreement was examined through raw agreement, Cohen's κ, Gwet's AC1 where applicable, confusion matrices, and per-class agreement. The question being measured matters: agreement that work or damage is **present** is not agreement on a specific catalog **code**. Calibration diagnostics are not final held-out performance claims. See [evidence and evaluation](docs/evidence-and-evaluation.md).

## Repository map

```text
README.md                         study overview
docs/source-card.md               source shapes and quality conditions
docs/method.md                    pipeline and controls
docs/evidence-and-evaluation.md  provenance and evaluation design
docs/engineering-findings.md     reviewed findings and next decisions
templates/                        signal-report template and blank CSV
LICENSE                           MIT License
```

## Reproduction and use

This repository supports **method review and reuse of the decision template**. It is not an end-to-end runner for the original study. Source-dependent computation requires a controlled environment, reference inputs, and data rights outside this publication. Readers can inspect the stages, adapt the scorecard, and apply the same evidence gates to their own authorized data.

Keep every figure tied to its target, source path, registration level, counting unit, eligible universe, evidence level, and source. Freeze thresholds and prototype construction before evaluating on held-out material. Never aggregate incompatible paths or infer code accuracy from an anchor count.

## Limits and next decisions

- No independently verified catalog-code precision or production threshold is claimed. LLM annotation is diagnostic, not human expert validation.
- Some semantic runs used a declared 128-token input limit; longer narratives may carry signal beyond that window.
- A profile restricts code eligibility, not correctness. Uncovered recurring concepts should be characterized as possible catalog or configuration gaps before being discarded.
- Component-level registration needs an explicit operator decision and independent human review.
- Daily snapshots need data-engineering episode reconstruction before estimated events can serve as completed maintenance histories.

The next modeling decision should be target-specific and path-specific. It depends on a valid evaluation set, the chosen registration level, and whether the destination catalog can express the text signal.

## Publications

For a deeper account of the engineering findings and contributions, see the forthcoming white paper and related publications. Links will appear here as they become available.

- Medium — white paper; link pending.
- Weights & Biases — related publication; link pending.
- LinkedIn — project summary; link pending.

## License

This repository includes the [MIT License](LICENSE).
