# Guided Preproduction

Use the same expert contract for every user. Guidance changes how missing decisions are explained, not what counts as ready.

## Plain-language intake

Begin with the user's scene intent and answer these in order only as needed:

1. What should the audience understand or feel by the end?
2. How many seconds does the shot have?
3. Where are the character and prop at the beginning and end?
4. What moves: character, camera, environment, or more than one?
5. Which direction does the action travel, and what do adjacent shots establish?
6. Which references control identity, prop, environment, boundaries, motion, camera, or audio?
7. Who approves the board and who may later authorize generation cost?

If an answer is missing but not needed yet, leave it alone. If it changes physical continuity or control, record it as unresolved and return `INPUT_REQUIRED`.

## Route the shot

- `dialogue-simple-acting`: emphasize eyeline, readable pose change, mouth/gesture timing, and restraint. Few beats may be enough.
- `multi-beat-action-prop-transition`: expose anticipation, contact/extreme, ownership change, follow-through, camera beats, and recovery. Use `multi-keyframe` unless a human redesigns the shot.
- `adjacent-continuity`: compare boundary state, travel direction, axis/eyeline, prop ownership, and what must match at the cut.

## Control-method conversation

Explain the methods without naming a provider:

- `text-only`: no visual reference controls the result;
- `single-keyframe`: one still anchors identity/composition;
- `start-end-keyframes`: two boundaries constrain a simple transition;
- `multi-keyframe`: several approved beats constrain action and camera progression; or
- `human-redesign`: the current shot should be split or re-staged before generation.

Do not claim that more references are always better. Each reference needs one primary role, an honest asset state, and a content digest when bytes exist; conflicting role instructions reduce control. A complex `multi-keyframe` route cannot become ready from a label alone—it needs at least three ready control frames referenced by the approved beats.

## Human review

Show the timed `shot-board.md` and its JSON source. Ask the human to approve the exact draft or name a change. Any creative change creates a new draft digest and needs a new approval receipt. Only then compile the shot contract.

## Handoff language

The generation handoff describes story function, duration, approved beats, camera motion, character motion, environment reaction, reference roles, rejection criteria, and unsupported quality claims. It ends with the machine state and the exact separately authorized next action. It never contains a provider purchase instruction.
