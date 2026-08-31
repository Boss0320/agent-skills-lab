#!/usr/bin/env python3
"""Validate a provider-neutral timed storyboard and its reference roles."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any
import unicodedata


BOARD_KEYS = {
    "shot_id",
    "duration_seconds",
    "board_state",
    "story_function",
    "route_class",
    "control_method",
    "screen_direction",
    "beats",
    "boundary_state",
    "adjacent_shots",
    "unresolved_decisions",
    "human_decision_owner",
    "approval",
}
BEAT_KEYS = {
    "beat_id",
    "start_seconds",
    "end_seconds",
    "composition",
    "character_motion",
    "camera_motion",
    "environment_reaction",
    "prop_state",
    "reference_ids",
}
BEAT_TEXT_FIELDS = {
    "composition",
    "character_motion",
    "camera_motion",
    "environment_reaction",
    "prop_state",
}
BOUNDARY_KEYS = {"start", "end"}
ADJACENT_KEYS = {"previous_screen_direction", "next_screen_direction"}
APPROVAL_KEYS = {"approver_id", "approved_at", "draft_sha256", "reference_roles_sha256"}
REFERENCE_DOCUMENT_KEYS = {"shot_id", "references"}
REFERENCE_KEYS = {"reference_id", "primary_role", "description", "asset_state", "content_sha256"}
BOARD_STATES = {"draft", "human_approved"}
ROUTE_CLASSES = {
    "dialogue-simple-acting",
    "multi-beat-action-prop-transition",
    "adjacent-continuity",
}
CONTROL_METHODS = {
    "text-only",
    "single-keyframe",
    "start-end-keyframes",
    "multi-keyframe",
    "human-redesign",
}
SCREEN_DIRECTIONS = {"left-to-right", "right-to-left", "static", "mixed"}
REFERENCE_ROLES = {"identity", "prop", "environment", "start", "end", "motion", "camera", "audio"}
ASSET_STATES = {"planned", "provided", "generated_unapproved", "human_approved"}
RESULT_KEYS = {"validation_status", "workflow_state", "next_action", "errors", "limitations"}
MAX_JSON_BYTES = 512 * 1024
EPSILON = 1e-9


class StoryboardDecodeError(ValueError):
    """Raised when a storyboard input cannot be decoded safely."""


def error(code: str, field: str, message: str) -> dict[str, str]:
    return {"code": code, "field": field, "message": message}


def limitations() -> list[str]:
    return [
        "Storyboard validation does not prove acting, physics, composition, taste, or finished video quality.",
        "Only a human-approved board may proceed to shot-contract compilation.",
        "Image or video generation and any spend require separate authorization.",
    ]


def result(
    validation_status: str,
    workflow_state: str | None,
    next_action: str,
    errors: list[dict[str, str]],
) -> dict[str, object]:
    value: dict[str, object] = {
        "validation_status": validation_status,
        "workflow_state": workflow_state,
        "next_action": next_action,
        "errors": errors,
        "limitations": limitations(),
    }
    assert set(value) == RESULT_KEYS
    return value


def _safe_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and value == unicodedata.normalize("NFC", value)
        and all(unicodedata.category(character) not in {"Cc", "Cf"} for character in value)
    )


def _safe_text_list(value: object, allow_empty: bool) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_safe_text(item) for item in value)
        and len(value) == len(set(value))
    )


def _finite_number(value: object, *, positive: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    return math.isfinite(number) and (number > 0 if positive else number >= 0)


def _valid_timestamp(value: object) -> bool:
    if not _safe_text(value):
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_references(
    references: object,
    shot_id: object,
) -> tuple[list[dict[str, str]], set[str], dict[str, dict[str, object]]]:
    errors: list[dict[str, str]] = []
    declared: set[str] = set()
    records: dict[str, dict[str, object]] = {}
    if not isinstance(references, dict):
        return [error("REFERENCES_TYPE_INVALID", "references", "Reference roles must be an object.")], declared, records
    if set(references) != REFERENCE_DOCUMENT_KEYS:
        errors.append(error("REFERENCES_KEYS_INVALID", "references", "Reference-role keys are not closed."))
        return errors, declared, records
    if references.get("shot_id") != shot_id:
        errors.append(error("SHOT_ID_MISMATCH", "references.shot_id", "Reference roles must bind the same shot."))
    items = references.get("references")
    if not isinstance(items, list):
        errors.append(error("REFERENCES_LIST_INVALID", "references.references", "References must be an array."))
        return errors, declared, records
    for index, item in enumerate(items):
        prefix = f"references.references[{index}]"
        if not isinstance(item, dict) or set(item) != REFERENCE_KEYS:
            errors.append(error("REFERENCE_KEYS_INVALID", prefix, "Reference keys are not closed."))
            continue
        reference_id = item.get("reference_id")
        if not _safe_text(reference_id):
            errors.append(error("REFERENCE_ID_INVALID", f"{prefix}.reference_id", "Reference ID must be safe text."))
        elif reference_id in declared:
            errors.append(error("REFERENCE_ID_DUPLICATE", f"{prefix}.reference_id", "Each reference receives one primary role."))
        else:
            declared.add(str(reference_id))
            records[str(reference_id)] = item
        if item.get("primary_role") not in REFERENCE_ROLES:
            errors.append(error("REFERENCE_ROLE_INVALID", f"{prefix}.primary_role", "Primary role is outside the closed enum."))
        if not _safe_text(item.get("description")):
            errors.append(error("REFERENCE_DESCRIPTION_INVALID", f"{prefix}.description", "Reference description must be safe text."))
        asset_state = item.get("asset_state")
        content_digest = item.get("content_sha256")
        if asset_state not in ASSET_STATES:
            errors.append(error("REFERENCE_ASSET_STATE_INVALID", f"{prefix}.asset_state", "Asset state is outside the closed enum."))
        elif asset_state == "planned":
            if content_digest is not None:
                errors.append(error("REFERENCE_DIGEST_PREMATURE", f"{prefix}.content_sha256", "A planned asset cannot claim content bytes."))
        elif not _valid_digest(content_digest):
            errors.append(error("REFERENCE_CONTENT_DIGEST_INVALID", f"{prefix}.content_sha256", "Available asset needs lowercase SHA-256."))
    return errors, declared, records


def validate_storyboard(board: object, references: object) -> dict[str, object]:
    schema_errors: list[dict[str, str]] = []
    input_errors: list[dict[str, str]] = []
    if not isinstance(board, dict):
        return result(
            "INVALID",
            None,
            "repair_artifact",
            [error("BOARD_TYPE_INVALID", "board", "Storyboard must be an object.")],
        )
    if set(board) != BOARD_KEYS:
        return result(
            "INVALID",
            None,
            "repair_artifact",
            [error("BOARD_KEYS_INVALID", "board", "Storyboard keys are not closed.")],
        )

    shot_id = board.get("shot_id")
    if not _safe_text(shot_id):
        schema_errors.append(error("SHOT_ID_INVALID", "shot_id", "Shot ID must be safe text."))
    duration = board.get("duration_seconds")
    if not _finite_number(duration, positive=True):
        schema_errors.append(error("NUMBER_INVALID", "duration_seconds", "Duration must be a finite positive number."))
    state = board.get("board_state")
    if state not in BOARD_STATES:
        schema_errors.append(error("BOARD_STATE_INVALID", "board_state", "Board state is outside the closed enum."))
    if board.get("route_class") not in ROUTE_CLASSES:
        schema_errors.append(error("ROUTE_CLASS_INVALID", "route_class", "Route class is outside the closed enum."))
    if board.get("control_method") not in CONTROL_METHODS:
        schema_errors.append(error("CONTROL_METHOD_INVALID", "control_method", "Control method is outside the closed enum."))

    story_function = board.get("story_function")
    if story_function is None:
        input_errors.append(error("STORY_FUNCTION_REQUIRED", "story_function", "Director must decide the story function."))
    elif not _safe_text(story_function):
        schema_errors.append(error("TEXT_INVALID", "story_function", "Story function must be safe text or null."))
    direction = board.get("screen_direction")
    if direction is None:
        input_errors.append(error("SCREEN_DIRECTION_REQUIRED", "screen_direction", "Screen direction remains unresolved."))
    elif direction not in SCREEN_DIRECTIONS:
        schema_errors.append(error("SCREEN_DIRECTION_INVALID", "screen_direction", "Screen direction is outside the closed enum."))

    role_errors, declared_references, reference_records = _validate_references(references, shot_id)
    schema_errors.extend(role_errors)

    beats = board.get("beats")
    valid_timings: list[tuple[float, float]] = []
    if not isinstance(beats, list):
        schema_errors.append(error("BEATS_TYPE_INVALID", "beats", "Beats must be an array."))
    elif not beats:
        input_errors.append(error("BEATS_REQUIRED", "beats", "At least one timed beat is required."))
    else:
        beat_ids: set[str] = set()
        for index, beat in enumerate(beats):
            prefix = f"beats[{index}]"
            if not isinstance(beat, dict) or set(beat) != BEAT_KEYS:
                schema_errors.append(error("BEAT_KEYS_INVALID", prefix, "Beat keys are not closed."))
                continue
            beat_id = beat.get("beat_id")
            if not _safe_text(beat_id) or beat_id in beat_ids:
                schema_errors.append(error("BEAT_ID_INVALID", f"{prefix}.beat_id", "Beat ID must be unique safe text."))
            else:
                beat_ids.add(str(beat_id))
            start = beat.get("start_seconds")
            end = beat.get("end_seconds")
            if not _finite_number(start) or not _finite_number(end, positive=True) or float(end) <= float(start or 0):
                schema_errors.append(error("BEAT_TIMING_INVALID", prefix, "Beat timing must be finite and increasing."))
            else:
                valid_timings.append((float(start), float(end)))
            for field in BEAT_TEXT_FIELDS:
                value = beat.get(field)
                if value is None:
                    input_errors.append(error("BEAT_DECISION_REQUIRED", f"{prefix}.{field}", "Beat decision remains unresolved."))
                elif not _safe_text(value):
                    schema_errors.append(error("TEXT_INVALID", f"{prefix}.{field}", "Beat field must be safe text or null."))
            reference_ids = beat.get("reference_ids")
            if not _safe_text_list(reference_ids, allow_empty=True):
                schema_errors.append(error("REFERENCE_IDS_INVALID", f"{prefix}.reference_ids", "Reference IDs must be a unique string array."))
            else:
                for reference_id in reference_ids:
                    if reference_id not in declared_references:
                        input_errors.append(error("REFERENCE_UNDECLARED", f"{prefix}.reference_ids", "Referenced input has no declared primary role."))
                    elif reference_records[reference_id].get("asset_state") not in {"provided", "human_approved"}:
                        input_errors.append(error("REFERENCE_ASSET_NOT_READY", f"{prefix}.reference_ids", "Referenced asset is planned or awaits human approval."))

    control_method = board.get("control_method")
    ready_used_references: set[str] = set()
    if isinstance(beats, list):
        for beat in beats:
            if not isinstance(beat, dict) or not isinstance(beat.get("reference_ids"), list):
                continue
            for reference_id in beat["reference_ids"]:
                record = reference_records.get(reference_id)
                if (
                    record
                    and record.get("asset_state") in {"provided", "human_approved"}
                    and record.get("primary_role") in {"start", "end", "motion", "camera"}
                ):
                    ready_used_references.add(reference_id)
    ready_roles = {
        reference_records[reference_id].get("primary_role")
        for reference_id in ready_used_references
    }
    control_missing = (
        (control_method == "single-keyframe" and len(ready_used_references) < 1)
        or (control_method == "start-end-keyframes" and not {"start", "end"} <= ready_roles)
        or (control_method == "multi-keyframe" and len(ready_used_references) < 3)
    )
    if control_missing:
        input_errors.append(error("CONTROL_REFERENCE_REQUIRED", "control_method", "Declared control method lacks enough ready, referenced control frames."))

    if isinstance(beats, list) and beats and len(valid_timings) == len(beats) and _finite_number(duration, positive=True):
        timing_invalid = not math.isclose(valid_timings[0][0], 0.0, abs_tol=EPSILON)
        for previous, current in zip(valid_timings, valid_timings[1:]):
            if not math.isclose(previous[1], current[0], abs_tol=EPSILON):
                timing_invalid = True
        if not math.isclose(valid_timings[-1][1], float(duration), abs_tol=EPSILON):
            timing_invalid = True
        if timing_invalid:
            schema_errors.append(error("BEAT_TIMING_INVALID", "beats", "Beats must cover the duration without gaps or overlap."))

    boundary = board.get("boundary_state")
    if not isinstance(boundary, dict) or set(boundary) != BOUNDARY_KEYS:
        schema_errors.append(error("BOUNDARY_STATE_INVALID", "boundary_state", "Boundary state must contain exact start and end keys."))
    else:
        for field in ("start", "end"):
            value = boundary.get(field)
            if value is None:
                input_errors.append(error("BOUNDARY_DECISION_REQUIRED", f"boundary_state.{field}", "Physical boundary remains unresolved."))
            elif not _safe_text(value):
                schema_errors.append(error("TEXT_INVALID", f"boundary_state.{field}", "Boundary must be safe text or null."))

    adjacent = board.get("adjacent_shots")
    if not isinstance(adjacent, dict) or set(adjacent) != ADJACENT_KEYS:
        schema_errors.append(error("ADJACENT_SHOTS_INVALID", "adjacent_shots", "Adjacent shots need exact previous and next keys."))
    else:
        for field in ADJACENT_KEYS:
            value = adjacent.get(field)
            if value is not None and value not in SCREEN_DIRECTIONS:
                schema_errors.append(error("SCREEN_DIRECTION_INVALID", f"adjacent_shots.{field}", "Adjacent direction is outside the closed enum."))

    unresolved = board.get("unresolved_decisions")
    if not _safe_text_list(unresolved, allow_empty=True):
        schema_errors.append(error("UNRESOLVED_DECISIONS_INVALID", "unresolved_decisions", "Unresolved decisions must be a unique string array."))
    elif unresolved:
        input_errors.append(error("DIRECTOR_DECISION_REQUIRED", "unresolved_decisions", "A declared director decision remains unresolved."))
    owner = board.get("human_decision_owner")
    if owner is None:
        input_errors.append(error("DECISION_OWNER_REQUIRED", "human_decision_owner", "Human decision owner is required."))
    elif not _safe_text(owner):
        schema_errors.append(error("TEXT_INVALID", "human_decision_owner", "Decision owner must be safe text or null."))

    approval = board.get("approval")
    if state == "draft" and approval is not None:
        schema_errors.append(error("DRAFT_APPROVAL_FORBIDDEN", "approval", "A draft cannot carry approval."))
    elif state == "human_approved":
        if not isinstance(approval, dict) or set(approval) != APPROVAL_KEYS:
            schema_errors.append(error("APPROVAL_REQUIRED", "approval", "Human-approved board needs an exact approval receipt."))
        else:
            if not _safe_text(approval.get("approver_id")):
                schema_errors.append(error("APPROVER_ID_INVALID", "approval.approver_id", "Approver ID must be safe text."))
            if not _valid_timestamp(approval.get("approved_at")):
                schema_errors.append(error("APPROVAL_TIME_INVALID", "approval.approved_at", "Approval time must include a timezone."))
            if not _valid_digest(approval.get("draft_sha256")):
                schema_errors.append(error("DRAFT_DIGEST_INVALID", "approval.draft_sha256", "Draft digest must be lowercase SHA-256."))
            if not _valid_digest(approval.get("reference_roles_sha256")):
                schema_errors.append(error("REFERENCE_APPROVAL_DIGEST_INVALID", "approval.reference_roles_sha256", "Reference-role digest must be lowercase SHA-256."))
            elif approval.get("reference_roles_sha256") != _canonical_sha256(references):
                schema_errors.append(error("REFERENCE_APPROVAL_DIGEST_MISMATCH", "approval.reference_roles_sha256", "Approval does not bind the supplied reference roles."))

    if schema_errors:
        return result("INVALID", None, "repair_artifact", schema_errors + input_errors)
    if input_errors:
        return result("VALID", "INPUT_REQUIRED", "request_input", input_errors)

    assert isinstance(adjacent, dict)
    conflicting = any(
        adjacent.get(field) in {"left-to-right", "right-to-left"}
        and direction in {"left-to-right", "right-to-left"}
        and adjacent.get(field) != direction
        for field in ADJACENT_KEYS
    )
    if conflicting:
        return result(
            "VALID",
            "SEQUENCE_REVIEW_REQUIRED",
            "resolve_sequence",
            [error("SCREEN_DIRECTION_CONFLICT", "adjacent_shots", "Adjacent travel direction conflicts with this shot.")],
        )
    if state == "draft":
        return result("VALID", "BOARD_DRAFT_READY", "request_board_approval", [])
    return result("VALID", None, "compile_shot_contract", [])


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise StoryboardDecodeError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> object:
    raise StoryboardDecodeError(f"invalid JSON constant: {value}")


def _load_json(path: Path, label: str) -> Any:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_JSON_BYTES:
            raise StoryboardDecodeError(f"{label} exceeds {MAX_JSON_BYTES} bytes")
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as caught:
        if isinstance(caught, StoryboardDecodeError):
            raise
        raise StoryboardDecodeError(f"{label} unreadable: {caught}") from caught


def _parse_arguments(arguments: list[str]) -> tuple[Path, Path] | None:
    if len(arguments) != 4:
        return None
    values: dict[str, str] = {}
    for index in range(0, len(arguments), 2):
        flag, value = arguments[index], arguments[index + 1]
        if flag not in {"--board", "--references"} or flag in values or not value or value.startswith("-"):
            return None
        values[flag] = value
    if set(values) != {"--board", "--references"}:
        return None
    return Path(values["--board"]), Path(values["--references"])


def main(arguments: list[str] | None = None) -> int:
    parsed = _parse_arguments(list(sys.argv[1:] if arguments is None else arguments))
    if parsed is None:
        value = result(
            "INVALID",
            None,
            "repair_artifact",
            [error("USAGE_INVALID", "arguments", "Use --board PATH --references PATH exactly once.")],
        )
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return 2
    board_path, references_path = parsed
    try:
        value = validate_storyboard(
            _load_json(board_path, "board"),
            _load_json(references_path, "references"),
        )
    except StoryboardDecodeError as caught:
        value = result(
            "INVALID",
            None,
            "repair_artifact",
            [error("JSON_INVALID", "input", str(caught))],
        )
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    if value["validation_status"] == "INVALID":
        return 2
    return 0 if value["next_action"] == "compile_shot_contract" else 1


if __name__ == "__main__":
    raise SystemExit(main())
