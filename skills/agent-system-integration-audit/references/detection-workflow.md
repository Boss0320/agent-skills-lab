# Detection-First Workflow

This workflow prevents taxonomy and packet formatting from substituting for an
actual integration audit. A dimension describes a supported observation; it is
not a search strategy and cannot create evidence.

## Guided mode

For a user who has only a broad concern, establish five inputs in plain
language:

1. the exact read-only root;
2. the changed or suspected behavior;
3. the expected end-to-end outcome;
4. the relevant entrypoint and final consumer; and
5. the focused checks that can run without mutation.

If the request is too broad, propose one bounded producer-to-consumer slice.
Do not describe an unexamined repository as fully audited.

## Expert mode

When the user supplies a frozen root, boundary contract, entrypoint, consumer,
and checks, confirm the scope once and begin the same kernel immediately. Expert
mode skips the intake conversation, not the evidence or validation gates.

## Expert kernel

1. **Freeze scope.** Enumerate the allowed regular files and reject symlink or
   root-escape paths. Verify a supplied manifest before interpreting behavior.
2. **Map the real route.** Identify the producer, every transformation or
   adapter that can change the record, the composition/configuration that selects
   the route, and the final consumer whose behavior matters.
3. **State the boundary contract.** Write the exact field, authority, event,
   ordering, identity, unit, period, fallback, or required-path behavior that
   must survive the route.
4. **Search against the first story.** Inspect at least one contradicting path
   and one bypass or alternate path. Record what was checked even when neither
   supports a defect.
5. **Probe with stated reach.** Run a focused read-only command and preserve its
   exact normalized-LF output. Say which producer, transformations, and consumer
   the command actually exercises; a component test has component reach only.
6. **Write `detection-record.json`.** Record the observed status, producer,
   consumer, boundary contract, evidence identities, contradicting and bypass
   paths, command/output/reach, unobserved paths, and residual risk. Do not put a
   dimension, severity, preferred finding ID, or evaluator assertion in it.
7. **Validate.** Run `scripts/validate_detection_record.py --input
   detection-record.json --root <frozen-root>`. It rejects symlink or escaping
   evidence and verifies each excerpt against the declared source line. An
   invalid record stops the workflow; prose cannot repair it.
8. **Classify only after detection.** If the valid record supports a finding,
   map it to the primary assessment dimension and justified secondary
   dimensions. If it does not, preserve the clean or insufficient-evidence
   observation without inventing a defect.
9. **Package last.** Build `audit-packet.json`, validate it, and write the human
   companion. Formatting cannot strengthen the underlying observation.

## Observed statuses

- `BOUNDARY_MISMATCH_OBSERVED`: evidence and the reach-bounded probe show that
  the producer-to-consumer route does not satisfy its stated contract. Dimension,
  consequence, and severity are still assigned later.
- `BOUNDARY_MATCH_OBSERVED`: the bounded route satisfies the stated contract.
  This is not a universal clean bill and does not erase unrelated minor issues.
- `INSUFFICIENT_EVIDENCE`: the permitted evidence cannot establish the route or
  consequence. Classification and approval language are unavailable.

## Required human explanation

Begin the final report with:

- **Outcome:** the bounded observation and typed packet status;
- **Why:** the decisive producer, consumer, contract, and command result;
- **Next safe action:** the next probe, human decision, or separately authorized
  repair step;
- **Not proven:** the unobserved paths and the strongest unsupported inference.

The audit stays read-only. A finding is not a fix, and a clean bounded probe is
not production or release approval.
