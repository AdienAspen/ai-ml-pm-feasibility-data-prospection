# Signal Report — Template

*A decision instrument for feasibility studies that map free text into a controlled vocabulary whose destination is configured per object (for example, ERP maintenance catalogs).*

The report answers, per decision unit: **is there signal, of what quality, and what is missing to use it?**
It decides whether a later ML modeling phase has a basis. It does **not** estimate how well a model would perform.

---

## 1 · Decision unit

One row per **target × source path × registration level**.

- **Target** — the field or catalog to be filled (e.g. damage, cause, object part).
- **Source path** — one data origin with its own counting unit (e.g. relational records, daily snapshots). Paths are never aggregated.
- **Registration level** — the level of the object hierarchy at which a record is registered; it selects the configuration profile and therefore the valid codes.

State the **counting unit** and the **eligible universe** (the denominator) for every row.

---

## 2 · Dimensions

Cell labels: **Pass · Partial · Fail · Not measured · Not applicable**. Write the supporting value next to the label (e.g. `Pass · 71.3%`).

| Dimension | Question | Metric | Pass | Partial | Fail | Origin |
|---|---|---|---|---|---|---|
| Presence | Is there signal? | % of the eligible universe with signal | ≥ 20% | 5–20% | < 5% | analyst decision |
| Consistency | Is it read the same way twice? | inter-annotator Cohen's κ · Gwet's AC1 as control | ≥ 0.80 | 0.60–0.80 | < 0.60 | Landis & Koch scale |
| Discrimination | Does it separate classes? | share of the top concept or code among signal units | ≤ 30% | 30–40% | > 40% | project convention |
| Expressibility | Can the destination receive it? | % of signal units with ≥ 1 code enabled by the profile at the registration level | ≥ 70% | 30–70% | < 30% | analyst decision |
| Dependency | What is missing to use it? | categorical: none · operator decision · data preparation | — | — | — | project convention |

Adjust thresholds to your domain, and keep the **Origin** column: thresholds that are analyst decisions are declared as such.

### Rules attached to the dimensions

- When κ and AC1 diverge because of prevalence, rate by κ and flag it.
- State which question each κ measured: **presence** of the target in the text, or the **code** itself.
- Ties above 50% lower discrimination by one level.
- Agreement measures consistency, not accuracy.

---

## 3 · Verdict rule

| Verdict | Condition |
|---|---|
| **Ready** | Every applicable dimension passes and there is no dependency. |
| **Conditional** | No dimension fails; dependencies become stated conditions. A "Not measured" consistency also lands here. |
| **Not ready** | Presence, consistency or expressibility fails. |
| **Not assessable** | The unit of analysis is not yet valid (e.g. snapshot records not yet reconstructed into episodes). |

Additional rules:

- Discrimination failing alone → **Conditional** (correctable by restricting candidates to the profile).
- If no precision has been validated, **no ML-addressable unit can be Ready**; only deterministic units (direct fields, structural joins) can.
- Report what the scorecard yields. Do not push a verdict toward or away from an ML phase.

---

## 4 · Scorecard

| Decision unit | Path | Level | Unit · universe | Presence | Consistency | Discrimination | Expressibility | Dependency | Verdict | Condition to change it |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |
| | | | | | | | | | | |
| | | | | | | | | | | |

**Constructed example row (not a study result):**

| Decision unit | Path | Level | Unit · universe | Presence | Consistency | Discrimination | Expressibility | Dependency | Verdict | Condition to change it |
|---|---|---|---|---|---|---|---|---|---|---|
| Example work category | relational | asset | record · 100 | Pass · 60% | Pass · κ 0.82 | Pass · 25% | Partial · 55% | operator decision | **Conditional** | confirm the registration level and code space |

---

## 5 · Reading guide

- **Ready** — resolved without a model; migrate from the field or the join.
- **Conditional** — signal exists and the destination can receive it once the stated conditions are met (e.g. registration level decided, precision measured on a blind human sample).
- **Not ready** — check *why*: scarce signal (presence), unstable reading (consistency) or a destination that cannot receive it (expressibility). The last one is resolved in configuration, not with a model.
- **Not assessable** — fix the unit of analysis first; this is usually data engineering.

Two gaps worth naming in the condition column:

- **Profile gap** — the code exists in the catalog, but the profile does not enable it.
- **Catalog gap** — the catalog has no code for a signal that is clearly present.

---

## 6 · Evidence levels

Tag every figure with one level and never present a proxy as verified accuracy:

`observed` · `validated` · `proxy` · `synthetic` · `inferred`

Keep a provenance column or footnote that names the source file of each figure.
