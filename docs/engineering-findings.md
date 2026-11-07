# Engineering findings and decisions

This document summarizes the engineering conclusions that determine what a later implementation could responsibly claim. It omits record-level examples and exact operational counts.

## Structure settles some targets

Direct material fields and asset-level functional-location joins have a different evidence status from inferred catalog codes. A structural asset match does not imply that a component leaf is known. Component resolution may depend on narrative text, item descriptions, and a valid hierarchy/profile path.

## Text signal and catalog expressibility diverge

The annotation rounds showed that maintenance work can be read consistently even when the permitted Activity codes rarely express the work described. Damage had usable group/code agreement when both annotators assigned a code, but the annotators differed in how readily they made an assignment. This makes **non-coverage** a first-class measure: recurring uncovered concepts may point to catalog content or profile-configuration work. They are characterized before any modeling decision.

## Detector choice changes measured volume

Exact lexical matching provides a conservative lexical floor. Semantic prototype matching yields a broader semantic estimate using the same frozen external vocabulary. Neither count is a validated precision estimate. The comparison is meaningful only on the same eligible universe, with prototype construction and threshold frozen before results are examined. Concept concentration helps distinguish a coarse source taxonomy from a detector that collapses onto one prototype.

## Registration level changes the answer space

The technical object's catalog profile restricts group and code choices. An asset-level profile and a candidate component profile can enable different code spaces. Profile resolution can remain possible when the component node is ambiguous, but that is a profile-level claim only. The registration level is therefore an operator decision with direct consequences for the classification task.

## Daily records require episode reconstruction

Daily reports contain repeated snapshots. Preliminary grouping reduced row counts, but did not establish completed intervention histories. Data engineering must create an event log, propose episode boundaries, identify completion, and validate a blind sample before these paths can be assessed at the order or notification level.

## Next decision gates

1. Confirm the intended registration level and profile configuration for each target.
2. Characterize recurring signal that has no eligible destination code.
3. Obtain independent human domain review for code correctness where a model is proposed.
4. Reconstruct and validate episodes for daily-report paths.
5. Train a supervised model only where the eligible volume and independent evaluation justify one.
