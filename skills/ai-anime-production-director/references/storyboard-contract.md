# Storyboard Contract

The storyboard stage makes creative staging inspectable before a shot contract or media request exists. It has two machine artifacts and one human companion:

- `shot-board.json` is the closed machine source of timed beats;
- `reference-roles.json` gives every supplied reference exactly one primary purpose; and
- `shot-board.md` explains the same board to a human and cannot override the JSON.

## Approval boundary

`board_state` is exactly `draft` or `human_approved`. A draft carries JSON `null` in `approval`. A human-approved board carries an exact receipt with `approver_id`, timezone-bearing `approved_at`, the lowercase SHA-256 of the draft that the human reviewed, and the canonical SHA-256 of the reviewed `reference-roles.json`. Silence, a model suggestion, a valid schema, or a generated still is never approval.

The validator may expose these workflow outcomes:

- `INPUT_REQUIRED`: a physical, timing, reference, or directorial decision is explicitly unresolved;
- `BOARD_DRAFT_READY`: a complete proposed board awaits human approval; or
- `SEQUENCE_REVIEW_REQUIRED`: adjacent travel direction conflicts with the proposed shot.

A clean human-approved board receives the next action `compile_shot_contract`; the board validator itself never emits `MOTION_PROOF_READY`.

## Timed beats

Beats cover the declared duration from zero to the exact end without overlap or gaps. Each beat separates composition, character motion, camera motion, environment reaction, and prop state. `reference_ids` point only to declarations in `reference-roles.json`.

The board also declares a closed `route_class` and provider-neutral `control_method`. The route is one of `dialogue-simple-acting`, `multi-beat-action-prop-transition`, or `adjacent-continuity`. The control method is one of `text-only`, `single-keyframe`, `start-end-keyframes`, `multi-keyframe`, or `human-redesign`. A later contract validator checks whether that method can actually control the approved route; it does not silently substitute a method.

Simple dialogue may need few beats. Fast action, prop transfer, transformation, or major camera movement should expose anticipation, readable extreme/contact, follow-through, and non-uniform timing when those decisions materially control the shot. Do not force a fixed panel count onto a trivial shot.

## Reference roles

Each reference ID appears once and has one primary role from `identity`, `prop`, `environment`, `start`, `end`, `motion`, `camera`, or `audio`. It also declares `asset_state` as `planned`, `provided`, `generated_unapproved`, or `human_approved`, plus a lowercase content SHA-256 when bytes exist. A planned reference carries JSON `null` instead of inventing a digest. A turnaround or detail sheet does not silently control pose, camera, or timing merely because it is present.

Referenced assets must be `provided` or `human_approved` before readiness. `single-keyframe` needs at least one ready referenced control frame, `start-end-keyframes` needs ready `start` and `end` roles, and `multi-keyframe` needs at least three ready control references actually used by the timed beats. Otherwise the board returns `INPUT_REQUIRED`.

## Limits

Passing structure does not prove acting, physics, composition, taste, continuity outside the supplied adjacent shots, or finished video quality. Image/video generation, provider choice, spend, and final creative acceptance remain separately authorized human decisions.
