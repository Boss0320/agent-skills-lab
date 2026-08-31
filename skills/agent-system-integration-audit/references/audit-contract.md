# Integration Audit Contract

## Purpose and boundary

This compact reference defines a deterministic, read-only assessment for an
invented software system. The assessor may inspect, compare, and report, but
has no edit, repair, mutation, deployment, or approval authority. No edit or
repair authority is implied by a finding, a command, or an audit result.

## Typed finding record

A finding is one closed JSON object with exactly the keys shown below. The
severity enum is exactly `CRITICAL`, `MATERIAL`, or `MINOR`. `dimension` is
the primary dimension. Later fixtures use one primary dimension and optional secondary dimensions. Each evidence item has exactly a string `path`, positive
integer `line`, and non-empty string `excerpt`.

Evidence must identify source actually inspected by the assessor. A valid
source location and sufficient observed behavior support the claim; secret
wording, a preferred finding identifier, or an undisclosed preferred line
cannot replace that evidence. Additional unique supporting evidence is allowed.
Duplicate portable identities are invalid.

`observed_output` may contain normalized LF (`\n`) line breaks so an exact
multiline command result can be preserved. Tabs, carriage returns, NUL, and all
other Unicode `Cc` or `Cf` controls remain forbidden.

```json
{
  "finding_id": "CASE-D04-F01",
  "severity": "CRITICAL",
  "dimension": 4,
  "secondary_dimensions": [],
  "claim": "The declared LanternQueue authority path bypasses its required gate.",
  "expected_impact": "An unapproved queue action could be accepted.",
  "evidence": [
    {
      "path": "src/lantern_router.py",
      "line": 18,
      "excerpt": "gate was skipped"
    }
  ],
  "verification_command": "python3 -m unittest tests.test_lantern_router -v",
  "observed_output": "FAILED: required gate was not called",
  "root_closed_by": "A regression named test_queue_calls_required_gate asserts the exact gate.",
  "residual_risk": "Other unmodeled LanternQueue routes remain outside this fixture."
}
```

`root_closed_by` always names concrete closure evidence; it does not claim that
the evidence has already closed the reported finding.

## Typed audit-result records

An audit result is one closed JSON object. Its status enum is exactly
`FINDINGS_REPORTED` or `CLEAN_CONTROL_PASS`. `FINDINGS_REPORTED` requires a
non-empty `findings` array of typed finding records. This envelope contains the
canonical finding exactly:

```json
{
  "status": "FINDINGS_REPORTED",
  "findings": [
    {
      "finding_id": "CASE-D04-F01",
      "severity": "CRITICAL",
      "dimension": 4,
      "secondary_dimensions": [],
      "claim": "The declared LanternQueue authority path bypasses its required gate.",
      "expected_impact": "An unapproved queue action could be accepted.",
      "evidence": [
        {
          "path": "src/lantern_router.py",
          "line": 18,
          "excerpt": "gate was skipped"
        }
      ],
      "verification_command": "python3 -m unittest tests.test_lantern_router -v",
      "observed_output": "FAILED: required gate was not called",
      "root_closed_by": "A regression named test_queue_calls_required_gate asserts the exact gate.",
      "residual_risk": "Other unmodeled LanternQueue routes remain outside this fixture."
    }
  ],
  "scope": "Synthetic LanternQueue authority fixture",
  "residual_risk": "Only the stated fixture path was assessed."
}
```

`CLEAN_CONTROL_PASS` requires an empty `findings` list, as in this clean
control:

```json
{
  "status": "CLEAN_CONTROL_PASS",
  "findings": [],
  "scope": "Synthetic LanternQueue clean-control fixture",
  "residual_risk": "Only the stated fixture path was assessed."
}
```

## Assessment dimensions

### Dimension 1: Dependency construction

Check dependency construction: required collaborators are created or injected
at the intended composition boundary with the declared lifetime.

### Dimension 2: Schema

Check shape/type compatibility for produced and consumed records, including
required fields and declared types.

### Dimension 3: Dataflow

Trace declared dataflow from input through transformations to its required sink;
identify drops, substitutions, or untracked derivations.

### Dimension 4: Authority

Check that a declared authority, approval, policy, or ownership node is reached
before its protected action and has no bypass route.

### Dimension 5: Configuration

Check configuration names, defaults, and precedence for the declared behavior
without hidden environment dependence.

### Dimension 6: Fallback behavior

Check fallback behavior when a dependency is unavailable; it must produce the
declared degraded result and not silently claim normal success.

### Dimension 7: Imports and declared dependencies

Check imports and declared dependencies for forbidden cycles, side-effect
initialization, and unavailable optional dependencies.

### Dimension 8: Adapter parity

Check adapter parity: interchangeable adapters preserve contract-relevant
fields, ordering, error shape, and declared semantics.

### Dimension 9: Events

Check events for stable names, required payload fields, and a traceable
producer-to-consumer path.

### Dimension 10: Instruction/prompt and callable-tool interface

Check instruction/prompt alignment with the available/required callable-tool
interface, including an unavailable/omitted capability.

### Dimension 11: Required path

Check the required path end to end with a focused reproducible command; an
isolated component result is not required path evidence.

### Dimension 12: Semantic correctness

Check semantic correctness of consumed parameters: identity, period, unit,
basis, freshness, derivation, and stale documentation must retain their
intended meaning.

Dimension 2 covers shape/type compatibility; Dimension 12 covers correct use and meaning.
This boundary makes finding attribution deterministic.

## Completion language

An audit is complete when each in-scope observation is reported or explicitly
marked unobserved with residual risk. Finding reported is not root closed.
Root closure requires separate evidence that a specified corrective change and
its regression check close that exact finding. An audit report is not a fix.

## Limits

This public example is project-neutral. It makes no claim of equivalence to any
other system, efficacy in every environment, universal coverage, publication
readiness, or deployment readiness.
