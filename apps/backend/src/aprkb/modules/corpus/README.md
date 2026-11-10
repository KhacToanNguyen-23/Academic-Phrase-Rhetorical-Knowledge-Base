# Corpus section detection

`SectionDetector.detect()` returns one code per parsed section and remains the ingest API.
`detect_with_provenance()` also reports whether a label came from a heading, inheritance,
an implicit parent opened by a subheading, position inference, or no match. Its `code` field
stays heading-derived; `inferred_code` carries the reporting-only METHODS inference. `detect()`
keeps heading-derived codes by default and exposes inference only when `infer_methods=True`.
A compound heading keeps the first matched code and exposes the second as `secondary_code`.
An unmatched numbered subheading can match its own heading; if its parent already has a label,
the parent label takes precedence and the child inherits it. The heading policy evaluates ordered
patterns within each code block, so specific METHODS prefixes precede generic RESULTS prefixes.

The narrow `long_methods_parent_override` policy is the documented exception: a benchmark,
evaluation, experiment, or experimental subheading with a configured setup/tool/measure term may
override a rhetorical top-section label for its own subtree. Siblings return to the parent code;
APPENDIX, REFERENCES, BACK_MATTER, and FIGURES_TABLES remain protected (`TODO(owner, FR-07)`).

The Markdown parser splits one heading line into parent and child/sibling headings only when the
embedded section number is a plausible immediate continuation. Number-only headings remain as
written because the parser cannot recover a missing title safely.

Arabic top headings may advance by the provisional `max_top_number_gap` in
`policies/section_headings.yaml`. The same policy holds the maximum heading length,
sentence-ending punctuation, and code keywords used to reject list and code lines. Its
vocabulary and thresholds remain provisional and require owner review.

Named theorem, lemma, proof, remark, corollary, proposition, claim, definition, and assumption
environments, along with lettered appendix subsections, map to `APPENDIX` and are excluded by the
mining noise policy. `formal_block_policy` controls whether a Definition or Assumption heading
inside METHODS inherits METHODS or is excluded; it defaults to `exclude` because the phase 1b
corpus check found three candidate sentences, none passing the mining filter and no extracted
frames. METHODS inference is reporting-only: ingest, filtering, and ownership continue to consume
`detect()` without inference.

The optional `apply_sandwich=True` argument on `detect_with_provenance()` is measurement-only
and defaults off. It assigns `source="sandwich"` to an UNKNOWN top-level section only when the
nearest heading-sourced sections on both sides have the same allowed code. Child sections inherit
the code; formal and non-rhetorical sections remain excluded. No ingest path enables this flag.

`scripts/section_label_report.py` verifies mining rights before reading corpus blobs. It
prints aggregate counts and never emits article body text.
