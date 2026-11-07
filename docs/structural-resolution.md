# Structural resolution and catalog scope

The component-resolution chain has distinct claims. A text mention can indicate a component without identifying a unique hierarchy node; a unique node can yield a catalog profile without validating a code; and a profile can allow codes without proving which code is correct.

## Resolution chain

1. Join the record to a known technical-object root using the source's structural key.
2. Detect component concepts in eligible, masked, normalized narrative text. Keep these concepts separate from catalog descriptions.
3. Restrict candidate nodes to descendants of that root. Exclude the root itself from component selection.
4. Resolve the node's effective profile by walking to the nearest ancestor with a valid profile. Record the number of levels walked; return `no_profile_no_filter` if no valid profile exists.
5. Compare detected concept labels with eligible node descriptions using normalized MiniLM vectors and cosine similarity. Each node takes its maximum score over all detected concepts.
6. Apply a frozen score threshold and a margin against the next candidate. A small margin yields an ambiguous node, not a fabricated selection.
7. For tied nodes, a profile may still resolve if **every** near-top node shares one valid profile. Node identity remains ambiguous.
8. Expand `profile → catalog type → allowed group → codes`. Report group counts and code counts separately.

The study's diagnostic node threshold was `0.60` with a `0.05` margin. These values do not establish independently validated component accuracy. [Public method code](../study_methods/profile_scope.py) shows profile inheritance, group-to-code expansion, and consensus without original hierarchy or catalog values.

## Evaluation boundary

If the same Object Part text signal chooses a component node and that node's profile restricts the code space, the resulting code decision is dependent on that text signal. Independent structural evidence is required to validate node resolution. Where it is unavailable, report the dependency.

Component-level and asset-level registration are different deliverables. Profile availability, candidate code availability, and correct code assignment are separate metrics.
