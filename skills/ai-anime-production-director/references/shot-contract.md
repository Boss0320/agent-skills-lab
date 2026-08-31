# Shot Contract

`shot-contract.json` is compiled from one `human_approved` storyboard and its `reference-roles.json`. It is a provider-neutral, testable description of causal motion. It is not a media request or a guarantee of a good clip.

## Provenance

The contract binds canonical JSON SHA-256 digests for the approved board and reference roles. Its copied approval receipt binds the exact draft that the human reviewed. The compiler rejects a draft, an unbound approval, or any post-approval change beyond the board's `board_state` and `approval` fields.

## Closed fields

| Field | Required decision |
|---|---|
| Shot and source identity | `shot_id`, approved-board digest, reference-role digest, and approval receipt. |
| Story and duration | Audience-facing change and exact positive duration. |
| Route and control | Closed `route_class` and provider-neutral `control_method`. |
| Key beats | Ordered board beats covering zero through the exact duration. |
| Physical boundaries | Character placement/orientation plus prop ownership at start and end. |
| Motion sources | Character, camera, and environment movement remain separate inside each beat. |
| Screen direction and adjacent shots | Travel direction and supplied previous/next direction. |
| Rejection criteria | Observable boundary, direction, and beat-order failures. |
| Authority | Human decision owner and `generation_authorized: false`. |

The compiler derives rejection criteria mechanically from the approved boundaries, direction, and beat order. It cannot add a new camera move, pose, prop transfer, or story beat.

## Workflow states

The validator uses only:

- `INPUT_REQUIRED` for explicit unresolved facts;
- `SEQUENCE_REVIEW_REQUIRED` for adjacent direction conflict;
- `SHOT_REDESIGN_REQUIRED` when the chosen control method cannot reliably express the route; and
- `MOTION_PROOF_READY` when the approved board and compiled contract pass structural checks.

`MOTION_PROOF_READY` means the shot may request a separately authorized cheap motion proof. It does not authorize that request by itself. Malformed JSON is an `INVALID` validation result, not a creative workflow state.

For a `multi-beat-action-prop-transition`, the public deterministic rule requires `multi-keyframe`; it does not pretend a single reference can control every approved pose and camera beat. `human-redesign` always returns `SHOT_REDESIGN_REQUIRED`.

## Limits

Structural readiness does not prove acting, physics, composition, taste, continuity beyond supplied boundaries, or finished video quality. A human retains final creative acceptance, provider choice, and any image/video spend.
