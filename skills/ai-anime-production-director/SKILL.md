---
name: ai-anime-production-director
description: Use when planning or reviewing a short AI-assisted animation shot, storyboard, camera move, action beat, reference package, motion-proof handoff, or adjacent-shot continuity before image or video generation.
---

# AI Anime Production Director

Turn directorial intent into a timed, inspectable preproduction package before any costly media work. Help a newcomer understand the next decision while preserving the same expert board, contract, validator, and human authority gate.

## Choose the operating depth

- **Guided mode:** start from a plain-language scene idea and explain only the
  next professional decision needed to form an inspectable board.
- **Expert mode:** accept a structured or `human_approved` board and move
  directly to the same validators and authority gates.

Start from the user's level in either mode.

Accept either:

- a plain-language scene idea;
- a draft storyboard;
- a `human_approved` storyboard and structured references; or
- an existing shot contract that needs validation or sequence review.

Ask only for the next missing fact that changes physical continuity, timing, reference use, control method, or authorization. Explain why it matters. Do not demand a full studio vocabulary before making a useful draft.

Silence is not approval. When the brief is silent and a staging choice is needed to make a draft readable, label it `proposed`, state the assumption, and name the human decision owner. An explicitly unresolved fact remains unresolved.

## Read the professional contracts

Use [guided preproduction](references/guided-preproduction.md) for the novice/expert routing, [the storyboard contract](references/storyboard-contract.md) for timed beats and reference roles, and [the shot contract](references/shot-contract.md) for compilation and readiness.

## Build the board before the shot contract

1. State the shot's story function: what changes for the audience during these seconds?
2. Identify duration, route class, screen direction, start/end physical state, prop ownership, adjacent-shot boundaries, and a provider-neutral control method.
3. Assign every supplied reference one primary role, honest asset state, and content digest in `reference-roles.json`. Identity, prop, environment, start, end, motion, camera, and audio are distinct purposes. A control method cannot be ready from a label without the required available control assets.
4. Produce `shot-board.json` as the machine source and `shot-board.md` as its plain-language companion.
5. For simple dialogue, use only the timed poses needed to make acting readable. For fast action, prop transfer, transformation, or major camera movement, expose anticipation, readable extreme/contact, follow-through, and non-uniform timing. Do not force a fixed panel count onto every shot.
6. Validate the board with `scripts/validate_storyboard.py`.
7. Stop at `BOARD_DRAFT_READY` until a human reviews the exact draft. A valid schema, model suggestion, or generated still cannot create approval.
8. After the exact draft becomes `human_approved`, compile `shot-contract.json` with `scripts/compile_shot_contract.py`. The compiler rejects post-approval creative drift.
9. Validate the compiled contract and produce `generation-handoff.md` with the bounded prompt recipe, reference roles, rejection criteria, unresolved decisions, and next authorized action.

## Closed workflow states

- `INPUT_REQUIRED`: a decision needed to form or compare the shot is explicitly unresolved.
- `BOARD_DRAFT_READY`: the proposed board is complete enough for human review, not generation.
- `SEQUENCE_REVIEW_REQUIRED`: adjacent shots or directorial choices conflict and a human must decide.
- `SHOT_REDESIGN_REQUIRED`: the shot or selected control method cannot reliably express the approved route.
- `MOTION_PROOF_READY`: the human-approved board and compiled contract pass structural checks and may request a separately authorized cheap motion proof.

Malformed JSON is an `INVALID` validation result, not a creative workflow state. Every non-ready state fails closed for downstream generation routing.

## Use the deterministic boundary

Validate a board and references:

```bash
python3 scripts/validate_storyboard.py --board shot-board.json --references reference-roles.json
```

Compile only the reviewed draft and its approved form:

```bash
python3 scripts/compile_shot_contract.py --draft draft/shot-board.json --board approved/shot-board.json --references approved/reference-roles.json --output approved/shot-contract.json
```

Revalidate the handoff sources:

```bash
python3 scripts/validate_shot_contract.py --contract shot-contract.json --board shot-board.json --references reference-roles.json
```

Do not weaken or paraphrase the machine state in prose.

## Return two layers

Begin the human response with:

1. **Outcome** — what was prepared or what blocked.
2. **Why** — the decisive evidence, conflict, or missing fact.
3. **Next safe action** — the exact human review or separately authorized step.
4. **Not proven** — the most important unsupported quality inference.

Return the declared JSON/Markdown artifacts for machine and expert inspection. The Markdown explains; JSON remains authoritative.

## Expert path

An expert who supplies a valid `human_approved` board and `reference-roles.json` may skip the guided interview. They do not skip the same compilation, provenance digests, control-method check, sequence review, or authority state.

## Boundaries

Keep examples invented and provider-neutral. Do not include private characters, worlds, assets, incidents, prices, job details, or accepted-shot formulas.

Do not automatically generate images or video. Do not select a provider. Do not authorize spend. Do not treat a generated board as human approval. A separate explicit request may authorize still-board generation or a cheap motion proof, but structural readiness alone never authorizes either.

`MOTION_PROOF_READY` does not prove acting, physics, composition, taste, character consistency, adjacent continuity outside supplied boundaries, or finished video quality. A human retains final creative acceptance and cost authority.
