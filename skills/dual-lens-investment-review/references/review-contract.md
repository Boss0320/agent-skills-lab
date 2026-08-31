# Dual-Lens Review Contract

## Governing principles

- Unknown is not zero. Missing disclosure remains `UNKNOWN`; do not convert it
  into a numeric fact, estimate, or source-backed claim.
- A material source-integrity failure has hard veto authority. It cannot be
  averaged against a useful narrative.
- Reviewer contexts are independent. Neither lens may read the other lens's
  prompt, output, transcript, or conclusion.
- Reconciliation is deterministic. It does not produce a third investment
  opinion.
- `READY_FOR_HUMAN_REVIEW` leaves the final decision with a human.

## Delivery state is separate from review semantics

Before dispatch, the controller selects one sink for both lens files:
`controller-capture` or `direct file`. The delivery validator accepts exactly
`lens-decision.json` and `lens-review.json`, enforces the case and lens identity,
checks agreement between the tiny and detailed results, records canonical
SHA-256 digests, and enforces the configured byte ceiling.

`UNAVAILABLE is not a lens disposition`. It is controller state meaning that a
complete, valid, isolated result bundle was not obtained. `UNAVAILABLE` carries
no `PASS`, `REVISE`, `BLOCK`, or reconciled verdict. The controller must not
repair a malformed bundle from prose or substitute another path, transcript, or
model call.

## Tiny semantic decision

Each lens writes `lens-decision.json` with exactly these keys:

```json
{
  "case_id": "CASE-SAMPLE",
  "lens": "decision_usability",
  "disposition": "PASS",
  "material_failure": false,
  "primary_claim_id": null,
  "primary_category": null
}
```

`lens` is `decision_usability` or `source_integrity`. `disposition` is `PASS`,
`REVISE`, or `BLOCK`. `material_failure` is Boolean. `PASS` and `REVISE`
require `false`; `BLOCK` requires `true`. A passing lens uses null primary
fields. A revising or blocking lens names the most decision-relevant claim and
one category allowed for that lens. These two fields let evaluation distinguish
the right conclusion from a lucky verdict without depending on detailed prose.

## Detailed usability review

`decision-usability/lens-review.json` has exactly:

```json
{
  "case_id": "CASE-SAMPLE",
  "lens": "decision_usability",
  "disposition": "REVISE",
  "material_failure": false,
  "findings": [],
  "residual_risk": "Source support is outside this lens."
}
```

The `findings` array is empty only for `PASS`. Each finding has exactly:

```json
{
  "finding_id": "U-01",
  "severity": "MINOR",
  "category": "DECISION_FRAME",
  "claim_ids": ["C1"],
  "summary": "The time horizon is not stated.",
  "evidence": [
    {"path": "report.md", "line": 4, "excerpt": "[C1] Revenue grew 14%."}
  ]
}
```

Usability categories are `THESIS`, `CATALYST`, `RISK`, `VALUATION`,
`CONTRADICTION`, `UNKNOWN_HANDLING`, and `DECISION_FRAME`.

## Detailed integrity review

`source-integrity/lens-review.json` has the usability keys plus
`claim_checks`. Each claim check has exactly:

```json
{
  "claim_id": "C1",
  "status": "SUPPORTED",
  "material": true,
  "source_refs": [
    {"path": "sources/filing.md", "line": 3, "excerpt": "Revenue was 114 million."}
  ]
}
```

Claim status is `SUPPORTED`, `CONTRADICTED`, or `UNKNOWN`. Integrity categories
are `SOURCE_SUPPORT`, `PERIOD`, `UNIT`, `BASIS`, `VALUATION_MEANING`,
`UNKNOWN_HANDLING`, and `INTERNAL_CONTRADICTION`.

## Severity and disposition

- `MATERIAL`: reasonably capable of changing the report's recommendation,
  valuation use, core risk framing, or decision readiness.
- `MINOR`: requires correction but does not control the thesis or action.
- `PASS`: no actionable finding; `material_failure=false`.
- `REVISE`: at least one actionable non-material finding;
  `material_failure=false`.
- `BLOCK`: at least one material finding; `material_failure=true`.

Apply the three-part materiality test in
`guided-intake-and-materiality.md`: exact issue, frozen evidence status, and
decision consequence. A source-integrity finding must overlap a claim check in
`CONTRADICTED` or `UNKNOWN` state. A `MATERIAL` source finding must overlap a
non-supported claim check with `material=true`; presentation polish alone does
not satisfy that rule.

Every finding needs a unique non-empty `finding_id`, at least one claim ID, and
at least one exact in-scope evidence location. Evidence paths are relative,
cannot contain `..`, and use positive line numbers and literal excerpts.

## Deterministic reconciliation

For schema-valid reviews with the same `case_id`:

1. `source_integrity` blocks or reports `material_failure=true` → `BLOCK`,
   `veto_source=source_integrity`.
2. Otherwise `decision_usability` blocks or reports `material_failure=true` →
   `BLOCK`, `veto_source=decision_usability`.
3. Otherwise either lens returns `REVISE` → `REVISE`, `veto_source=none`.
4. Otherwise both lenses must return `PASS` → `READY_FOR_HUMAN_REVIEW`,
   `veto_source=none`.

The reconciler output includes the case ID, verdict, veto source, accepted
findings with their originating lens, canonical SHA-256 of each detailed review,
and residual risk from both lenses. Validation errors produce no verdict.
