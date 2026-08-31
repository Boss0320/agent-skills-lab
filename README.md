# Agent Skills Lab

[繁體中文](README.zh-TW.md)

Three reusable workflow packages for AI work: trace a defect across an agent
system, review investment research without mixing two independent judgments,
and turn a scene brief into an approved shot contract before generation.

This is not a prompt gallery. Each clean-room Skill combines guided intake,
an expert workflow, machine-readable artifacts, deterministic validators,
synthetic failure cases, and an explicit human authority boundary.

For the dated repository and publication state, see
[`PUBLICATION_STATUS.md`](PUBLICATION_STATUS.md).

## What each Skill lets you do

### 1. Find the seam that broke the system

[`agent-system-integration-audit`](skills/agent-system-integration-audit/SKILL.md)
takes a bounded, read-only system root and follows the real producer-to-consumer
path before it classifies a finding. It returns a neutral detection record, an
evidence-bound audit packet, and the remaining unobserved risk. It never grants
itself repair authority.

In the frozen synthetic paired set, professional packet quality moved from
**0/3 → 2/3**. Semantic defect detection stayed **3/3 → 3/3**. The measured
benefit was a more usable, traceable audit delivery—not a model that suddenly
found more defects.

### 2. Keep a persuasive report from outrunning its sources

[`dual-lens-investment-review`](skills/dual-lens-investment-review/SKILL.md)
separates decision usability from source integrity in two isolated review
contexts. A typed delivery boundary freezes both reviews before deterministic
reconciliation; a material source-integrity failure can veto publication.

Valid lens delivery moved from **0/6 → 6/6**, and reconciliation moved from
**0/3 → 3/3**. Raw reasoning lift was not scored. The Skill demonstrates
delivery discipline, evidence binding, materiality, and review governance—not
investment performance or trading advice.

### 3. Make the shot inspectable before generation

[`ai-anime-production-director`](skills/ai-anime-production-director/SKILL.md)
turns directorial intent into a timed storyboard, declared reference roles, a
human approval receipt, and a compiled shot contract. Conflicts stop at a human
decision gate; the Skill never silently authorizes image/video generation or
spend.

Valid storyboard/workflow artifacts moved from **0/2 → 2/2**. Blind preference
was unavailable, and Finished-media quality remains unproven. The evidence is
about preproduction structure and fail-closed handoff, not whether the final
animation looks better.

## What the evidence means

The current result is an offline quality regrade of 25 preserved result
receipts. It added zero model calls and kept the original failures. Each case
currently has one paired run, so the aggregate is useful local evidence—not a
statistically strong public benchmark.

The exact machine-readable results live in
[`evidence/benchmark-summary.json`](evidence/benchmark-summary.json), with a
plain-language explanation in [`evidence/README.md`](evidence/README.md).
The governing claims gate is `EXPAND_BEFORE_PUBLIC_CLAIMS`.

This package does not prove general intelligence uplift, raw-reasoning lift for
Skill B, finished-media quality, investment performance, production
certification, or universal behavior across models and tasks.

## Package shape

- `skills/` — three independently installable clean-room Skills.
- `scripts/` — package assembly, evidence, and disclosure-boundary tooling.
- `tests/` — contract, regression, malformed-input, fixture, and package tests.
- `evidence/` — sanitized aggregate results and limitations; no raw model transcripts.
- `provenance/` — public file provenance, rights inventory, and manifest.

## Verify locally

From the repository root, run the standard-library suite twice exactly as shown:

```sh
python3 -m unittest discover -s tests
python3 -m unittest discover -s tests
```

The second run is intentional: it verifies that normal Python bytecode caches do
not break the packaged publication contracts. Neither command requires `-B`.

## Rights and release state

The approved repository slug is `agent-skills-lab`. The contents are provided
for portfolio review and evaluation under the evaluation-only
[`LICENSE`](LICENSE); they are not open source and may not be reused, modified,
or redistributed without prior written permission from Titus Lai.

The dated repository and publication-state ledger is maintained in
[`PUBLICATION_STATUS.md`](PUBLICATION_STATUS.md); later owner-controlled
visibility changes do not rewrite its historical rows.
