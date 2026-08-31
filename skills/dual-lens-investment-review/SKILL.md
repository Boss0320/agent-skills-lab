---
name: dual-lens-investment-review
description: Review investment-research reports through context-isolated decision-usability and source-integrity lenses, then reconcile them with deterministic veto rules. Use whenever the user asks for an evidence-backed research-report review, investment memo quality gate, claim-source audit, period/unit/basis check, or decision-readiness review, even when the prose and arithmetic look polished.
---

# Dual-Lens Investment Review

Use this Skill to review a supplied investment-research artifact without making
an investment decision for the user. The workflow separates “Can a human use
this report to decide?” from “Do the supplied sources actually support it?” so
persuasive prose cannot average away a source-integrity failure.

Read `references/review-contract.md` and
`references/guided-intake-and-materiality.md` before dispatching either lens.
Their closed schemas, category definitions, materiality rules, and
reconciliation states are authoritative.

Choose exactly one result sink before dispatch and put it in both reviewer
instructions:

- `controller-capture`: the controller captures one JSON envelope whose `files`
  object contains exactly `lens-decision.json` and `lens-review.json`; or
- `direct file`: the reviewer writes those two files beneath its assigned lens
  directory.

Do not mix sinks within a call or recover a missing file from prose, a transcript,
or another path. After each reviewer returns, run
`scripts/validate_lens_delivery.py` against the selected sink. Only an
`AVAILABLE` delivery may be frozen and used later. Missing, malformed,
mismatched, oversized, or non-isolated delivery becomes controller state
`UNAVAILABLE`; it produces no lens disposition and no reconciled verdict. Do
not repair, retry, or reinterpret it inside this workflow.

## Required inputs

- The report to review, with stable claim IDs when available.
- A decision context describing the intended decision, horizon, and constraints.
- The finite source packet that the report claims to rely on.
- A real isolation mechanism such as fresh subagents or separate clean model
  invocations.

Do not fetch missing sources, infer live market state, or treat absent data as
zero. If the environment cannot provide two genuinely isolated reviewer
contexts, say that the full dual-lens workflow cannot be completed. Do not fake
isolation with two headings in one model response.

## Choose the operating depth

- **Guided mode:** help a non-specialist identify the decision, horizon,
  constraints, report, finite sources, and material claim IDs. Missing fields
  remain explicit; the Skill never fabricates the packet.
- **Expert mode:** accept an already structured packet and move straight to
  boundary freeze, lens isolation, and review. Do not repeat beginner intake.

Both modes converge on the same expert contract and validators. Guided mode is
an interface layer, not a lower quality standard.

## Freeze the input boundary

1. Normalize the packet root so reviewer paths are `report.md`,
   `decision-context.md`, and `sources/...`; do not silently add or remove a
   wrapper directory.
2. Record the exact in-scope files and SHA-256 digests before review.
3. Reject symlinks, paths escaping the supplied root, unlisted source files, or
   mutable live links.
4. Give both lenses the same frozen report bytes and public review contract.
5. Keep expected findings, grading catalogs, prior conversation, and other
   reviewer output outside both contexts.

## Dispatch `decision_usability`

Start a fresh reviewer that receives only:

- the frozen report;
- the decision context;
- the public review contract;
- the instruction to act as `decision_usability`.

It must not receive source documents, the `source_integrity` prompt or output,
hidden expected answers, or prior reviewer conversation. It assesses thesis
clarity, decision framing, catalysts, risks, valuation use, contradictions,
Unknown handling, and whether the report separates fact from inference.

Require the selected sink to deliver `lens-decision.json` for the tiny semantic
result and `lens-review.json` for evidence-backed details. Validate the delivery,
then freeze both before continuing.

## Dispatch `source_integrity`

Start a different fresh reviewer that receives only:

- the identical frozen report;
- the finite frozen source packet;
- the public review contract;
- the instruction to act as `source_integrity`.

It must not receive the decision context, the `decision_usability` prompt or
output, hidden expected answers, or prior reviewer conversation. It checks each
material claim for source support, period, unit, basis, valuation meaning,
Unknown handling, and internal consistency. It never repairs missing evidence
with memory or external research.

Require the selected sink to deliver its own `lens-decision.json` and
`lens-review.json`; validate the delivery, then freeze both.

## Reconcile without another opinion

Run `scripts/reconcile_reviews.py` on the two validated delivery bundles only
after both have state `AVAILABLE` and are frozen. The public CLI accepts
`--usability-delivery` and `--integrity-delivery`; it rejects an unavailable or
post-validation-tampered bundle before producing a verdict.
The script validates closed schemas, verifies matching case identity, records
reviewer digests, and applies the contract's rules:

- a material source-integrity failure is a hard veto to `BLOCK`;
- a material decision-usability failure also blocks;
- a non-material actionable issue produces `REVISE`;
- only two passing lenses produce `READY_FOR_HUMAN_REVIEW`.

Do not ask a third model to average, rank, rewrite, or overrule the two reviews.
Malformed or mismatched input means no verdict, not a guessed fallback.

## Required deliverables

Return a directory containing:

- `decision-usability/lens-decision.json`;
- `decision-usability/lens-review.json`;
- `source-integrity/lens-decision.json`;
- `source-integrity/lens-review.json`;
- `reconciled-review.json` from the deterministic script;
- `review-report.md`, a human-readable summary that preserves the typed verdict.

The Markdown report must state the reviewed scope, reviewer isolation, frozen
input digests, accepted findings with provenance, veto source, unobserved paths,
and residual risk. It may explain but cannot weaken or extend the JSON verdict.

## Human and machine handoff

Begin the human response with:

1. **Outcome** — the reconciled state or the exact reason no verdict exists.
2. **Why** — the decisive lens finding, source limitation, or delivery failure.
3. **Next safe action** — the correction, missing evidence, or human review
   needed next.
4. **Not proven** — the strongest investment, source, or performance inference
   the bounded review does not establish.

The JSON artifacts remain authoritative for machine consumers. Markdown may
explain them but cannot create a missing disposition, weaken a veto, or turn
`UNAVAILABLE` into a review result.

## Completion language

`READY_FOR_HUMAN_REVIEW` means the supplied synthetic or user-provided evidence
passed these two review lenses. It is not approval to trade, a forecast, proof
of investment performance, or production certification. The human owns the
final decision and any request for new data, broader diligence, or action.
