#!/usr/bin/env python3
"""Validate a shot contract compiled from a human-approved storyboard."""

from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any
import unicodedata


CONTRACT_KEYS = {
    "shot_id", "approved_board_sha256", "reference_roles_sha256", "approval",
    "story_function", "duration_seconds", "route_class", "control_method",
    "screen_direction", "key_beats", "start_physical_state", "end_physical_state",
    "prop_state", "adjacent_shots", "rejection_criteria", "human_decision_owner",
    "generation_authorized",
}
BEAT_KEYS = {
    "beat_id", "start_seconds", "end_seconds", "composition", "character_motion",
    "camera_motion", "environment_reaction", "prop_state", "reference_ids",
}
BEAT_TEXT_FIELDS = {
    "composition", "character_motion", "camera_motion", "environment_reaction", "prop_state",
}
APPROVAL_KEYS = {"approver_id", "approved_at", "draft_sha256", "reference_roles_sha256"}
PROP_KEYS = {"start", "end"}
ADJACENT_KEYS = {"previous_screen_direction", "next_screen_direction"}
ROUTE_CLASSES = {
    "dialogue-simple-acting", "multi-beat-action-prop-transition", "adjacent-continuity",
}
CONTROL_METHODS = {
    "text-only", "single-keyframe", "start-end-keyframes", "multi-keyframe", "human-redesign",
}
SCREEN_DIRECTIONS = {"left-to-right", "right-to-left", "static", "mixed"}
MAX_JSON_BYTES = 512 * 1024
EPSILON = 1e-9
SCRIPT_ROOT = Path(__file__).resolve().parent
STORYBOARD_VALIDATOR = SCRIPT_ROOT / "validate_storyboard.py"


class ContractDecodeError(ValueError):
    """Raised when a contract input cannot be decoded safely."""


def error(code: str, field: str, message: str) -> dict[str, str]:
    return {"code": code, "field": field, "message": message}


def limitations() -> list[str]:
    return [
        "Structural readiness does not prove acting, physics, composition, taste, continuity beyond supplied boundaries, or finished video quality.",
        "MOTION_PROOF_READY permits only a separately authorized cheap motion proof.",
        "A human owns final creative acceptance, provider choice, and any generation spend.",
    ]


def result(validation_status: str, workflow_state: str | None, next_action: str, errors: list[dict[str, str]]) -> dict[str, object]:
    return {
        "validation_status": validation_status,
        "workflow_state": workflow_state,
        "next_action": next_action,
        "errors": errors,
        "limitations": limitations(),
    }


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and value == unicodedata.normalize("NFC", value)
        and all(unicodedata.category(character) not in {"Cc", "Cf"} for character in value)
    )


def _safe_text_list(value: object, allow_empty: bool = False) -> bool:
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


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _valid_timestamp(value: object) -> bool:
    if not _safe_text(value):
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def rejection_criteria_for(board: dict[str, object]) -> list[str]:
    boundary = board["boundary_state"]
    assert isinstance(boundary, dict)
    direction = board["screen_direction"]
    return [
        f"Reject if the start boundary differs: {boundary['start']}",
        f"Reject if the end boundary differs: {boundary['end']}",
        f"Reject if screen direction is not {direction}.",
        "Reject if any approved timed beat is omitted, reordered, or merged.",
    ]


def _load_storyboard_validator():
    spec = importlib.util.spec_from_file_location("storyboard_validator_for_shot_contract", STORYBOARD_VALIDATOR)
    if spec is None or spec.loader is None:
        raise ContractDecodeError("cannot load storyboard validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_parity_errors(
    contract: dict[str, object],
    approved_board: object,
    references: object,
) -> list[dict[str, str]]:
    if not isinstance(approved_board, dict) or not isinstance(references, dict):
        return [error("SOURCE_ARTIFACTS_INVALID", "source", "Board and reference roles must be objects.")]
    storyboard = _load_storyboard_validator()
    board_result = storyboard.validate_storyboard(approved_board, references)
    if board_result.get("next_action") != "compile_shot_contract":
        return [error("SOURCE_BOARD_INVALID", "approved_board", "Source board is not valid and clear for compilation.")]
    beats = approved_board["beats"]
    boundary = approved_board["boundary_state"]
    assert isinstance(beats, list) and beats and isinstance(boundary, dict)
    expected = {
        "shot_id": approved_board["shot_id"],
        "approved_board_sha256": canonical_sha256(approved_board),
        "reference_roles_sha256": canonical_sha256(references),
        "approval": approved_board["approval"],
        "story_function": approved_board["story_function"],
        "duration_seconds": approved_board["duration_seconds"],
        "route_class": approved_board["route_class"],
        "control_method": approved_board["control_method"],
        "screen_direction": approved_board["screen_direction"],
        "key_beats": beats,
        "start_physical_state": boundary["start"],
        "end_physical_state": boundary["end"],
        "prop_state": {"start": beats[0]["prop_state"], "end": beats[-1]["prop_state"]},
        "adjacent_shots": approved_board["adjacent_shots"],
        "rejection_criteria": rejection_criteria_for(approved_board),
        "human_decision_owner": approved_board["human_decision_owner"],
        "generation_authorized": False,
    }
    mismatches = sorted(field for field, value in expected.items() if contract.get(field) != value)
    if not mismatches:
        return []
    return [
        error(
            "CONTRACT_BOARD_PARITY_MISMATCH",
            "contract",
            "Contract differs from the bound approved board: " + ", ".join(mismatches),
        )
    ]


def _validate_beats(beats: object, duration: object) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    schema_errors: list[dict[str, str]] = []
    input_errors: list[dict[str, str]] = []
    if not isinstance(beats, list) or not beats:
        return [error("KEY_BEATS_INVALID", "key_beats", "Key beats must be a non-empty array.")], input_errors
    timings: list[tuple[float, float]] = []
    beat_ids: set[str] = set()
    for index, beat in enumerate(beats):
        prefix = f"key_beats[{index}]"
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
            timings.append((float(start), float(end)))
        for field in BEAT_TEXT_FIELDS:
            value = beat.get(field)
            if value is None:
                input_errors.append(error("BEAT_DECISION_REQUIRED", f"{prefix}.{field}", "Beat decision remains unresolved."))
            elif not _safe_text(value):
                schema_errors.append(error("TEXT_INVALID", f"{prefix}.{field}", "Beat field must be safe text or null."))
        if not _safe_text_list(beat.get("reference_ids"), allow_empty=True):
            schema_errors.append(error("REFERENCE_IDS_INVALID", f"{prefix}.reference_ids", "Reference IDs must be a unique string array."))
    if len(timings) == len(beats) and _finite_number(duration, positive=True):
        invalid = not math.isclose(timings[0][0], 0.0, abs_tol=EPSILON)
        for previous, current in zip(timings, timings[1:]):
            if not math.isclose(previous[1], current[0], abs_tol=EPSILON):
                invalid = True
        if not math.isclose(timings[-1][1], float(duration), abs_tol=EPSILON):
            invalid = True
        if invalid:
            schema_errors.append(error("BEAT_TIMING_INVALID", "key_beats", "Beats must cover the duration without gaps or overlap."))
    return schema_errors, input_errors


def validate_contract(contract: object, approved_board: object | None = None, references: object | None = None) -> dict[str, object]:
    if not isinstance(contract, dict):
        return result("INVALID", None, "repair_artifact", [error("CONTRACT_TYPE_INVALID", "contract", "Contract must be an object.")])
    if set(contract) != CONTRACT_KEYS:
        return result("INVALID", None, "repair_artifact", [error("CONTRACT_KEYS_INVALID", "contract", "Contract keys are not closed.")])

    schema_errors: list[dict[str, str]] = []
    input_errors: list[dict[str, str]] = []
    for field in ("shot_id", "story_function", "human_decision_owner"):
        value = contract.get(field)
        if value is None:
            input_errors.append(error("DECISION_REQUIRED", field, f"{field} remains unresolved."))
        elif not _safe_text(value):
            schema_errors.append(error("TEXT_INVALID", field, f"{field} must be safe text or null."))
    for field in ("approved_board_sha256", "reference_roles_sha256"):
        if not _digest(contract.get(field)):
            schema_errors.append(error("DIGEST_INVALID", field, f"{field} must be lowercase SHA-256."))
    approval = contract.get("approval")
    if not isinstance(approval, dict) or set(approval) != APPROVAL_KEYS:
        schema_errors.append(error("APPROVAL_INVALID", "approval", "Approval receipt keys are not closed."))
    elif (
        not _safe_text(approval.get("approver_id"))
        or not _valid_timestamp(approval.get("approved_at"))
        or not _digest(approval.get("draft_sha256"))
        or not _digest(approval.get("reference_roles_sha256"))
    ):
        schema_errors.append(error("APPROVAL_INVALID", "approval", "Approval receipt values are invalid."))
    elif approval.get("reference_roles_sha256") != contract.get("reference_roles_sha256"):
        schema_errors.append(error("REFERENCE_APPROVAL_DIGEST_MISMATCH", "approval.reference_roles_sha256", "Approval and contract must bind the same reference roles."))
    duration = contract.get("duration_seconds")
    if not _finite_number(duration, positive=True):
        schema_errors.append(error("NUMBER_INVALID", "duration_seconds", "Duration must be a finite positive number."))
    route_class = contract.get("route_class")
    control_method = contract.get("control_method")
    direction = contract.get("screen_direction")
    if route_class not in ROUTE_CLASSES:
        schema_errors.append(error("ROUTE_CLASS_INVALID", "route_class", "Route class is outside the closed enum."))
    if control_method not in CONTROL_METHODS:
        schema_errors.append(error("CONTROL_METHOD_INVALID", "control_method", "Control method is outside the closed enum."))
    if direction not in SCREEN_DIRECTIONS:
        schema_errors.append(error("SCREEN_DIRECTION_INVALID", "screen_direction", "Screen direction is outside the closed enum."))
    beat_errors, beat_inputs = _validate_beats(contract.get("key_beats"), duration)
    schema_errors.extend(beat_errors)
    input_errors.extend(beat_inputs)

    for field in ("start_physical_state", "end_physical_state"):
        value = contract.get(field)
        if value is None:
            input_errors.append(error("BOUNDARY_STATE_REQUIRED", field, "Physical boundary remains unresolved."))
        elif not _safe_text(value):
            schema_errors.append(error("TEXT_INVALID", field, "Physical boundary must be safe text or null."))
    prop_state = contract.get("prop_state")
    if not isinstance(prop_state, dict) or set(prop_state) != PROP_KEYS:
        schema_errors.append(error("PROP_STATE_INVALID", "prop_state", "Prop state needs exact start and end keys."))
    else:
        for field in ("start", "end"):
            value = prop_state.get(field)
            if value is None:
                code = "PROP_START_STATE_REQUIRED" if field == "start" else "PROP_END_STATE_REQUIRED"
                input_errors.append(error(code, f"prop_state.{field}", "Prop boundary remains unresolved."))
            elif not _safe_text(value):
                schema_errors.append(error("TEXT_INVALID", f"prop_state.{field}", "Prop boundary must be safe text or null."))
        beats = contract.get("key_beats")
        if isinstance(beats, list) and beats and all(isinstance(item, dict) for item in beats):
            if prop_state.get("start") is not None and prop_state.get("start") != beats[0].get("prop_state"):
                schema_errors.append(error("PROP_BOUNDARY_MISMATCH", "prop_state.start", "Prop start must match the first approved beat."))
            if prop_state.get("end") is not None and prop_state.get("end") != beats[-1].get("prop_state"):
                schema_errors.append(error("PROP_BOUNDARY_MISMATCH", "prop_state.end", "Prop end must match the last approved beat."))
    adjacent = contract.get("adjacent_shots")
    if not isinstance(adjacent, dict) or set(adjacent) != ADJACENT_KEYS:
        schema_errors.append(error("ADJACENT_SHOTS_INVALID", "adjacent_shots", "Adjacent shots need exact previous and next keys."))
    else:
        for field in ADJACENT_KEYS:
            value = adjacent.get(field)
            if value is not None and value not in SCREEN_DIRECTIONS:
                schema_errors.append(error("SCREEN_DIRECTION_INVALID", f"adjacent_shots.{field}", "Adjacent direction is outside the closed enum."))
    if not _safe_text_list(contract.get("rejection_criteria")):
        schema_errors.append(error("REJECTION_CRITERIA_INVALID", "rejection_criteria", "Rejection criteria must be a unique non-empty string array."))
    if contract.get("generation_authorized") is not False:
        schema_errors.append(error("GENERATION_AUTHORITY_INVALID", "generation_authorized", "Compilation cannot authorize generation."))
    sources_supplied = approved_board is not None or references is not None
    sources_complete = approved_board is not None and references is not None
    if sources_supplied and not sources_complete:
        schema_errors.append(error("SOURCE_ARTIFACTS_INCOMPLETE", "source", "Board and reference roles must be supplied together."))
    elif sources_complete:
        if contract.get("approved_board_sha256") != canonical_sha256(approved_board):
            schema_errors.append(error("BOARD_DIGEST_MISMATCH", "approved_board_sha256", "Contract does not bind the supplied approved board."))
        if contract.get("reference_roles_sha256") != canonical_sha256(references):
            schema_errors.append(error("REFERENCE_DIGEST_MISMATCH", "reference_roles_sha256", "Contract does not bind the supplied reference roles."))
        schema_errors.extend(_source_parity_errors(contract, approved_board, references))
    if schema_errors:
        return result("INVALID", None, "repair_artifact", schema_errors + input_errors)
    if input_errors:
        return result("VALID", "INPUT_REQUIRED", "request_input", input_errors)

    assert isinstance(adjacent, dict)
    conflict = any(
        adjacent.get(field) in {"left-to-right", "right-to-left"}
        and direction in {"left-to-right", "right-to-left"}
        and adjacent.get(field) != direction
        for field in ADJACENT_KEYS
    )
    if conflict:
        return result("VALID", "SEQUENCE_REVIEW_REQUIRED", "resolve_sequence", [error("SCREEN_DIRECTION_CONFLICT", "adjacent_shots", "Adjacent travel direction conflicts with this shot.")])
    incompatible = (
        control_method == "human-redesign"
        or (route_class == "multi-beat-action-prop-transition" and control_method != "multi-keyframe")
        or (route_class == "adjacent-continuity" and control_method == "text-only")
    )
    if incompatible:
        return result("VALID", "SHOT_REDESIGN_REQUIRED", "redesign_shot_or_control_method", [error("CONTROL_METHOD_INCOMPATIBLE", "control_method", "The declared method cannot reliably control this route class.")])
    if not sources_complete:
        return result("VALID", "INPUT_REQUIRED", "supply_bound_source_artifacts", [error("SOURCE_ARTIFACTS_REQUIRED", "source", "Approved board and reference roles are required before readiness can be established.")])
    return result("VALID", "MOTION_PROOF_READY", "request_separate_motion_proof_authorization", [])


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ContractDecodeError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> object:
    raise ContractDecodeError(f"invalid JSON constant: {value}")


def _load_json(path: Path, label: str) -> Any:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_JSON_BYTES:
            raise ContractDecodeError(f"{label} exceeds {MAX_JSON_BYTES} bytes")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as caught:
        if isinstance(caught, ContractDecodeError):
            raise
        raise ContractDecodeError(f"{label} unreadable: {caught}") from caught


def _parse_arguments(arguments: list[str]) -> tuple[Path, Path, Path] | None:
    if len(arguments) != 6:
        return None
    values: dict[str, str] = {}
    allowed = {"--contract", "--board", "--references"}
    for index in range(0, len(arguments), 2):
        flag, value = arguments[index], arguments[index + 1]
        if flag not in allowed or flag in values or not value or value.startswith("-"):
            return None
        values[flag] = value
    if set(values) != allowed:
        return None
    return Path(values["--contract"]), Path(values["--board"]), Path(values["--references"])


def main(arguments: list[str] | None = None) -> int:
    parsed = _parse_arguments(list(sys.argv[1:] if arguments is None else arguments))
    if parsed is None:
        value = result("INVALID", None, "repair_artifact", [error("USAGE_INVALID", "arguments", "Use --contract PATH --board PATH --references PATH exactly once.")])
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return 2
    contract_path, board_path, references_path = parsed
    try:
        value = validate_contract(_load_json(contract_path, "contract"), _load_json(board_path, "board"), _load_json(references_path, "references"))
    except ContractDecodeError as caught:
        value = result("INVALID", None, "repair_artifact", [error("JSON_INVALID", "input", str(caught))])
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    if value["validation_status"] == "INVALID":
        return 2
    return 0 if value["workflow_state"] == "MOTION_PROOF_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
