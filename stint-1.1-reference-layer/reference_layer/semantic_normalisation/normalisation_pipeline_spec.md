# Normalization pipeline specification

This specification records the sequence used to prepare maintenance text for lexical and semantic work. It is a methodological contract, not a claim that the text is correctly classified.

## Sequence

1. Mask equipment tags, record IDs, serial-like strings, dates, and counters before lexical matching.
2. Lowercase, normalize spacing, and remove punctuation that carries no domain meaning.
3. Expand abbreviations through a separately governed dictionary. Preserve the source and version of every expansion rule.
4. Correct spelling conservatively against an accepted reference entry.
5. Route normalized spans to candidate domain concepts, then consider structural nodes and destination catalog codes as separate links.

## Controls

- Do not translate every text before matching. Use a multilingual encoder where appropriate and keep language-specific aliases explicit.
- Preserve the source text field and source path on every derived signal.
- Keep event and maintenance strata separate when counting denominators.
- A lexical match is a candidate, not a validated code assignment.
- Do not construct the vocabulary from records held out for evaluation.
- Mask any serialized target assignment before extraction so it cannot become a feature.

The controlled run used a versioned normalization implementation. This public specification omits the private abbreviation dictionary and source-specific masking patterns.
