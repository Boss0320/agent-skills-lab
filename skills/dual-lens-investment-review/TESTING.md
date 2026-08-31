# Testing Dual-Lens Investment Review

## Current state

The candidate, four synthetic pilot cases, typed contracts, and deterministic
reconciler are locally testable. No model benchmark has run, so this file makes
no behavioral-uplift claim.

## Deterministic checks

From the Agent Skills Lab candidate root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_dual_lens_contract \
  tests.test_dual_lens_delivery \
  tests.test_dual_lens_materiality \
  tests.test_dual_lens_reconciler \
  tests.test_dual_lens_fixtures -v
```

These tests check clean-room structure, context-isolation language, the
controller-capture/direct-file delivery boundary, closed review schemas,
materiality relationships, source-integrity veto behavior, deterministic
digests, invented fixture identities, and exact visible manifest hashes.

The delivery validator emits one `AVAILABLE` or `UNAVAILABLE` JSON result. The
reconciler CLI accepts only the two frozen `AVAILABLE` delivery bundles and
refuses to overwrite an existing result:

```bash
python3 skills/dual-lens-investment-review/scripts/reconcile_reviews.py \
  --usability-delivery decision-usability/validated-delivery.json \
  --integrity-delivery source-integrity/validated-delivery.json \
  --output reconciled-review.json
```

## Future isolated pilot

The sealed internal arena plans 16 reviewer invocations:

```text
4 cases × 2 configurations × 2 isolated lenses = 16 calls
```

Every call receives one lens only. `decision_usability` cannot see source files;
`source_integrity` cannot see decision context. Neither sees the other output or
the hidden catalog. The deterministic reconciler runs only after both reviewer
outputs are frozen.

Future execution requires a fresh bounded authorization. A call failure is
recorded with planned score zero and is not retried or replaced. The initial
gate includes no blind comparator or model analyzer call.

## Claim boundary

Passing deterministic tests proves contract and fixture behavior only. It does
not prove reviewer capability, investment performance, alpha, deployment, or
public readiness.
