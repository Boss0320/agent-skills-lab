# Guided Intake and Materiality

This reference changes the amount of guidance, not the quality bar. Guided and
Expert mode must produce the same frozen packet, isolated lenses, typed files,
delivery validation, and deterministic reconciliation.

## Guided mode

Use Guided mode when the user does not already have a review packet. Ask for or
help label these six items without inventing any of them:

1. **Decision:** What real choice will this report inform?
2. **Horizon:** When could that choice be made or revisited?
3. **Constraints:** What price, risk, mandate, liquidity, or evidence limits
   matter?
4. **Report:** Which exact file is the claim-bearing report?
5. **Sources:** Which finite files does the report claim to rely on?
6. **Claim map:** Which stable claim IDs carry the thesis, valuation, catalysts,
   and principal risks?

If the user cannot answer a field, record it as missing. Do not silently fill it
from memory or the live market. A missing decision context prevents a meaningful
decision-usability review; a missing source remains `UNKNOWN` for source
integrity.

## Expert mode

Use Expert mode when the user supplies a packet root, decision context, stable
claim IDs, and finite sources. Confirm the root and scope in one compact line,
then proceed directly to freezing and isolation. Do not force the user through
the Guided questions again.

## Materiality test

For every proposed finding, write down three things before selecting severity:

1. the exact claim or omission;
2. what the frozen evidence does or does not establish; and
3. the **decision consequence** if the issue were corrected.

Use `MATERIAL` only when that consequence could reasonably change the report's
recommendation, valuation use, core risk framing, or readiness for the stated
decision. Use `MINOR` for an actionable correction that does not control those
outcomes. A `polish-only` preference—tone, formatting, stylistic compression,
or wording with no decision consequence—is not automatically a finding and can
never justify `BLOCK` by itself.

## UNKNOWN, contradiction, and disposition

- `UNKNOWN` means the frozen packet does not establish the claim. It never means
  zero and is never silently converted into an estimate.
- A non-material `UNKNOWN` with an actionable gap produces `REVISE`.
- A material `UNKNOWN` may produce `BLOCK` when the missing support is necessary
  for the stated decision.
- A material contradiction between a claim and its supplied source produces
  `BLOCK`.
- A non-material contradiction produces `REVISE`.
- A source-integrity finding must point to at least one matching claim check.
  `MATERIAL` severity must overlap a non-supported check marked material.

The lens does not decide materiality by how embarrassing an error looks. It
decides by the consequence for the stated decision.

## Human boundary

The system may say that the frozen report is ready for human review. It does not
approve a trade, select a security, predict returns, or replace the user's final
judgment.
