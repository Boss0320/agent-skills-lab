#!/usr/bin/env python3
"""Compile one human-approved storyboard into a provider-neutral shot contract."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
STORYBOARD_VALIDATOR = SCRIPT_ROOT / "validate_storyboard.py"
SHOT_VALIDATOR = SCRIPT_ROOT / "validate_shot_contract.py"


class CompilationError(ValueError):
    """Raised when an approved board cannot be compiled without invention."""


def _load_sibling(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CompilationError(f"cannot load required validator: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _approved_matches_draft(draft: object, approved: object) -> bool:
    if not isinstance(draft, dict) or not isinstance(approved, dict):
        return False
    normalized = deepcopy(approved)
    normalized["board_state"] = "draft"
    normalized["approval"] = None
    return normalized == draft


def compile_contract(
    draft: object,
    approved: object,
    references: object,
) -> dict[str, object]:
    storyboard = _load_sibling(STORYBOARD_VALIDATOR, "storyboard_validator_for_compiler")
    draft_result = storyboard.validate_storyboard(draft, references)
    if draft_result.get("workflow_state") != "BOARD_DRAFT_READY":
        raise CompilationError("draft must be a complete board awaiting approval")
    assert isinstance(draft, dict)
    assert isinstance(approved, dict)
    assert isinstance(references, dict)
    approval = approved.get("approval")
    if not isinstance(approval, dict):
        raise CompilationError("board must be human-approved and clear for compilation")
    if approval.get("reference_roles_sha256") != canonical_sha256(references):
        raise CompilationError("approval reference-role digest does not match supplied references")
    approved_result = storyboard.validate_storyboard(approved, references)
    if approved_result.get("next_action") != "compile_shot_contract":
        raise CompilationError("board must be human-approved and clear for compilation")
    if not _approved_matches_draft(draft, approved):
        raise CompilationError("human-approved board differs from approved draft")
    if approval.get("draft_sha256") != canonical_sha256(draft):
        raise CompilationError("approval draft digest does not match the reviewed draft")

    beats = deepcopy(approved["beats"])
    assert isinstance(beats, list) and beats
    boundary = approved["boundary_state"]
    assert isinstance(boundary, dict)
    direction = approved["screen_direction"]
    validator = _load_sibling(SHOT_VALIDATOR, "shot_validator_for_compiler")
    contract: dict[str, object] = {
        "shot_id": approved["shot_id"],
        "approved_board_sha256": canonical_sha256(approved),
        "reference_roles_sha256": canonical_sha256(references),
        "approval": deepcopy(approval),
        "story_function": approved["story_function"],
        "duration_seconds": approved["duration_seconds"],
        "route_class": approved["route_class"],
        "control_method": approved["control_method"],
        "screen_direction": direction,
        "key_beats": beats,
        "start_physical_state": boundary["start"],
        "end_physical_state": boundary["end"],
        "prop_state": {
            "start": beats[0]["prop_state"],
            "end": beats[-1]["prop_state"],
        },
        "adjacent_shots": deepcopy(approved["adjacent_shots"]),
        "rejection_criteria": validator.rejection_criteria_for(approved),
        "human_decision_owner": approved["human_decision_owner"],
        "generation_authorized": False,
    }
    validation = validator.validate_contract(contract, approved, references)
    if validation.get("validation_status") != "VALID":
        raise CompilationError("compiled contract failed structural validation")
    return contract


def _invalid(message: str) -> dict[str, object]:
    return {
        "validation_status": "INVALID",
        "workflow_state": None,
        "next_action": "repair_artifact",
        "errors": [{"code": "COMPILATION_FAILED", "field": "input", "message": message}],
        "limitations": [
            "No shot contract was written.",
            "Compilation never grants image/video generation or spend authority.",
        ],
    }


def _parse_arguments(arguments: list[str]) -> tuple[Path, Path, Path, Path] | None:
    if len(arguments) != 8:
        return None
    values: dict[str, str] = {}
    allowed = {"--draft", "--board", "--references", "--output"}
    for index in range(0, len(arguments), 2):
        flag, value = arguments[index], arguments[index + 1]
        if flag not in allowed or flag in values or not value or value.startswith("-"):
            return None
        values[flag] = value
    if set(values) != allowed:
        return None
    return (
        Path(values["--draft"]),
        Path(values["--board"]),
        Path(values["--references"]),
        Path(values["--output"]),
    )


def main(arguments: list[str] | None = None) -> int:
    parsed = _parse_arguments(list(sys.argv[1:] if arguments is None else arguments))
    if parsed is None:
        print(json.dumps(_invalid("Use --draft PATH --board PATH --references PATH --output PATH exactly once."), separators=(",", ":"), sort_keys=True))
        return 2
    draft_path, board_path, references_path, output_path = parsed
    try:
        storyboard = _load_sibling(STORYBOARD_VALIDATOR, "storyboard_loader_for_compiler")
        draft: Any = storyboard._load_json(draft_path, "draft")
        board: Any = storyboard._load_json(board_path, "board")
        references: Any = storyboard._load_json(references_path, "references")
        contract = compile_contract(draft, board, references)
        if output_path.exists() or output_path.is_symlink():
            raise CompilationError("output path already exists")
        if output_path.parent.is_symlink() or not output_path.parent.is_dir():
            raise CompilationError("output parent must be an existing non-symlink directory")
        validator = _load_sibling(SHOT_VALIDATOR, "shot_validator_for_compiler_cli")
        validation = validator.validate_contract(contract, board, references)
        output_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (CompilationError, OSError, ValueError) as caught:
        print(json.dumps(_invalid(str(caught)), ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        return 2
    print(json.dumps(validation, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0 if validation["workflow_state"] == "MOTION_PROOF_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
