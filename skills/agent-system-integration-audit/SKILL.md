---
name: agent-system-integration-audit
description: Audit multi-module agent systems after cross-file changes, new tools, adapter updates, configuration changes, prompt changes, event wiring, or authority-flow changes. Use this Skill whenever the user asks for an integration audit, end-to-end wiring review, semantic contract check, or evidence-backed release review, even when unit tests are already green.
---

# Agent System Integration Audit

Use this Skill to perform a read-only, evidence-backed review of how a software
system behaves across module boundaries. Inspect the supplied project without
editing, repairing, formatting, installing, deploying, or mutating its bytes.
The audit reports what is observed; it does not grant approval or fix defects.

The workflow is detection-first. Produce and validate a neutral
`detection-record.json` with `scripts/validate_detection_record.py` before
assigning any assessment dimension or building `audit-packet.json`. Read
`references/detection-workflow.md` for the required producer-to-consumer route,
contradicting and bypass searches, focused probe, and explicit reach.

## Required inputs

- The project or fixture root to inspect.
- The requested scope and any focused verification command supplied by the user.
- `references/audit-contract.md`, which is authoritative for the twelve
  dimensions, closed finding schema, result envelope, severity, and completion
  language.
- If present, the fixture's `case-manifest.json`, used only to bind its bytes
  and exact scope.

Do not infer missing source, configuration, runtime state, or test output. Mark
anything not observed in `residual_risk`.

## Choose the operating depth

- **Guided mode:** help the user bound one route by identifying the read-only
  root, suspected behavior, expected outcome, entrypoint, consumer, and safe
  checks. Missing runtime evidence remains unobserved.
- **Expert mode:** accept a pre-bounded route and proceed directly to the same
  detection kernel. The expert may skip intake questions, not validation.

## Read-only procedure

1. Record the exact root and enumerate the files that are actually in scope.
   Reject a symlinked root or any path that escapes it.
2. If a fixture manifest is present, verify its listed file hashes before
   assessing behavior. The audit packet `scope` must equal the manifest's exact
   `case_id`; a friendly project name is not a substitute.
3. Trace declared contracts across their real producer, adapter, composition,
   configuration, delegation, and consumer boundaries. A local component
   result is evidence only for that component.
4. State the exact boundary contract, then inspect contradicting behavior and
   bypass or alternate routes instead of stopping at the declared happy path.
5. Run only focused, deterministic, read-only checks that are available in the
   supplied project. Preserve the exact command and observed output, normalize
   output line endings to LF, keep every line boundary, and state the command's
   actual reach through producer, transformations, and consumer. Set
   `PYTHONDONTWRITEBYTECODE=1` for Python checks.
6. Reconcile the neutral observation with exact `path`, positive `line`, and
   source excerpt. Write `detection-record.json`; it contains observed facts and
   reach, not dimensions, severity, or evaluation answers.
7. Run `scripts/validate_detection_record.py --input detection-record.json
   --root <frozen-root>`. The validator binds evidence excerpts to exact regular
   files and source lines. Stop on invalid input. Read
   `references/audit-contract.md` and classify only after the detection record
   is valid; use its dimension definitions instead of inventing or renaming
   dimensions.
8. Reconcile every classified claim with the detection evidence.
   Keep every unique source identity needed to support the claim; do not discard
   supporting identities merely to produce one evidence item. Use one primary
   dimension and only justified secondary dimensions.
9. Recheck the result against the closed schemas in the reference. Derive every
   finding from inspected source and observed behavior, never from a grading
   label or asserted answer.
10. Return all required deliverables: `detection-record.json`,
   `audit-packet.json`, and `audit-report.md`. Do not modify the audited project
   to produce them.

## Evidence discipline

local green tests do not prove integration. They may omit the one assertion
that crosses a producer-consumer or adapter-contract boundary. Report the exact
reach of each command and keep untested paths in residual risk.

Use `FINDINGS_REPORTED` only with at least one fully typed finding. Use
`CLEAN_CONTROL_PASS` only when no in-scope material finding is supported and
describe the unobserved surface. Do not add keys to either envelope.

Never use unverified Accept language. A reported finding is not a verified fix,
and `root_closed_by` names the concrete evidence that would establish root
closure; it must not claim that root closure already happened. Never claim
universal coverage, efficacy, deployment readiness, or publication readiness.

## `audit-report.md` structure

Write a compact human-readable companion with:

1. `Outcome`, `Why`, `Next safe action`, and `Not proven` in plain language.
2. Scope and byte/hash status.
3. Commands executed and their exact outputs and reach.
4. Findings, each mapped to its packet `finding_id` and evidence identity.
5. Unobserved paths and residual risk.
6. A statement that the audit was read-only and made no changes.

The Markdown report may explain the JSON packet, but it cannot weaken,
override, or silently extend the typed packet.
