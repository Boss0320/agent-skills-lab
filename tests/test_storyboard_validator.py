from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "ai-anime-production-director" / "scripts" / "validate_storyboard.py"
FIXTURES = ROOT / "skills" / "ai-anime-production-director" / "fixtures"


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_validator():
    if not SCRIPT.is_file():
        raise AssertionError(f"missing storyboard validator: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("storyboard_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_board(state: str = "draft") -> dict[str, object]:
    approval = None
    if state == "human_approved":
        approval = {
            "approver_id": "synthetic-director",
            "approved_at": "2026-08-30T20:00:00Z",
            "draft_sha256": "a" * 64,
            "reference_roles_sha256": canonical_sha256(valid_roles()),
        }
    return {
        "shot_id": "SHOT-SWORD-01",
        "duration_seconds": 5.0,
        "board_state": state,
        "story_function": "The guard turns hesitation into a committed charge.",
        "route_class": "multi-beat-action-prop-transition",
        "control_method": "multi-keyframe",
        "screen_direction": "left-to-right",
        "beats": [
            {
                "beat_id": "B1",
                "start_seconds": 0.0,
                "end_seconds": 1.2,
                "composition": "Waist-level medium close view.",
                "character_motion": "Right hand closes on the sword grip.",
                "camera_motion": "Rise from waist toward the face.",
                "environment_reaction": "Loose cloth settles before acceleration.",
                "prop_state": "Sword remains sheathed and owned by the guard.",
                "reference_ids": ["CHAR-FRONT", "SWORD-DETAIL", "BOARD-START"],
            },
            {
                "beat_id": "B2",
                "start_seconds": 1.2,
                "end_seconds": 3.0,
                "composition": "Head-and-torso view opens to a wider frame.",
                "character_motion": "Sword clears the waist and rises overhead.",
                "camera_motion": "Continue rising, then begin a pullback.",
                "environment_reaction": "Hair and sash lag behind the lift.",
                "prop_state": "Sword is overhead in the guard's right hand.",
                "reference_ids": ["CHAR-SIDE", "SWORD-DETAIL", "BOARD-MID"],
            },
            {
                "beat_id": "B3",
                "start_seconds": 3.0,
                "end_seconds": 5.0,
                "composition": "Wide view preserves forward travel space.",
                "character_motion": "Guard leans forward and charges right.",
                "camera_motion": "Pull back while holding the travel axis.",
                "environment_reaction": "Dust and cloth trail the acceleration.",
                "prop_state": "Sword remains overhead in the right hand.",
                "reference_ids": ["CHAR-FRONT", "CHAR-SIDE", "BOARD-END"],
            },
        ],
        "boundary_state": {
            "start": "Guard faces right with sword sheathed at the left waist.",
            "end": "Guard travels right with sword overhead in the right hand.",
        },
        "adjacent_shots": {"previous_screen_direction": None, "next_screen_direction": None},
        "unresolved_decisions": [],
        "human_decision_owner": "Director",
        "approval": approval,
    }


def valid_roles() -> dict[str, object]:
    return {
        "shot_id": "SHOT-SWORD-01",
        "references": [
            {
                "reference_id": "CHAR-FRONT",
                "primary_role": "identity",
                "description": "Front identity and costume anchor.",
                "asset_state": "provided",
                "content_sha256": "1" * 64,
            },
            {
                "reference_id": "CHAR-SIDE",
                "primary_role": "motion",
                "description": "Side silhouette for the forward lean.",
                "asset_state": "provided",
                "content_sha256": "2" * 64,
            },
            {
                "reference_id": "SWORD-DETAIL",
                "primary_role": "prop",
                "description": "Sword hilt and guard geometry.",
                "asset_state": "provided",
                "content_sha256": "3" * 64,
            },
            {
                "reference_id": "BOARD-START",
                "primary_role": "start",
                "description": "Human-approved first control frame.",
                "asset_state": "human_approved",
                "content_sha256": "4" * 64,
            },
            {
                "reference_id": "BOARD-MID",
                "primary_role": "motion",
                "description": "Human-approved overhead extreme control frame.",
                "asset_state": "human_approved",
                "content_sha256": "5" * 64,
            },
            {
                "reference_id": "BOARD-END",
                "primary_role": "end",
                "description": "Human-approved charge boundary frame.",
                "asset_state": "human_approved",
                "content_sha256": "6" * 64,
            },
        ],
    }


class StoryboardValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_validator()

    def test_valid_draft_is_board_draft_ready(self) -> None:
        result = self.module.validate_storyboard(valid_board(), valid_roles())
        self.assertEqual("VALID", result["validation_status"])
        self.assertEqual("BOARD_DRAFT_READY", result["workflow_state"])
        self.assertEqual("request_board_approval", result["next_action"])

    def test_missing_decision_is_input_required(self) -> None:
        board = valid_board()
        board["story_function"] = None
        board["unresolved_decisions"] = ["Director must choose the emotional turn."]
        result = self.module.validate_storyboard(board, valid_roles())
        self.assertEqual("INPUT_REQUIRED", result["workflow_state"])
        self.assertEqual("request_input", result["next_action"])

    def test_adjacent_direction_conflict_requires_sequence_review(self) -> None:
        board = valid_board("human_approved")
        board["adjacent_shots"]["previous_screen_direction"] = "right-to-left"
        result = self.module.validate_storyboard(board, valid_roles())
        self.assertEqual("SEQUENCE_REVIEW_REQUIRED", result["workflow_state"])
        self.assertIn("SCREEN_DIRECTION_CONFLICT", {item["code"] for item in result["errors"]})

    def test_approved_clean_board_is_valid_for_compile_not_motion_proof(self) -> None:
        result = self.module.validate_storyboard(valid_board("human_approved"), valid_roles())
        self.assertEqual("VALID", result["validation_status"])
        self.assertIsNone(result["workflow_state"])
        self.assertEqual("compile_shot_contract", result["next_action"])
        self.assertNotEqual("MOTION_PROOF_READY", result["workflow_state"])

    def test_non_objects_and_extra_keys_are_invalid(self) -> None:
        non_object = self.module.validate_storyboard([], valid_roles())
        self.assertEqual("INVALID", non_object["validation_status"])
        board = valid_board()
        board["secret_shortcut"] = True
        extra = self.module.validate_storyboard(board, valid_roles())
        self.assertIn("BOARD_KEYS_INVALID", {item["code"] for item in extra["errors"]})

    def test_wrong_types_and_nonfinite_numbers_are_invalid(self) -> None:
        board = valid_board()
        board["duration_seconds"] = True
        board["beats"][0]["reference_ids"] = "CHAR-FRONT"
        result = self.module.validate_storyboard(board, valid_roles())
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("NUMBER_INVALID", codes)
        self.assertIn("REFERENCE_IDS_INVALID", codes)

        infinite = valid_board()
        infinite["duration_seconds"] = float("inf")
        self.assertIn(
            "NUMBER_INVALID",
            {item["code"] for item in self.module.validate_storyboard(infinite, valid_roles())["errors"]},
        )

    def test_route_class_and_control_method_are_closed(self) -> None:
        board = valid_board()
        board["route_class"] = "cinematic"
        board["control_method"] = "magic"
        result = self.module.validate_storyboard(board, valid_roles())
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("ROUTE_CLASS_INVALID", codes)
        self.assertIn("CONTROL_METHOD_INVALID", codes)

    def test_overlapping_gapped_or_out_of_range_beats_are_invalid(self) -> None:
        cases = []
        overlap = valid_board()
        overlap["beats"][1]["start_seconds"] = 1.0
        cases.append(overlap)
        gap = valid_board()
        gap["beats"][1]["start_seconds"] = 1.3
        cases.append(gap)
        outside = valid_board()
        outside["beats"][-1]["end_seconds"] = 5.1
        cases.append(outside)
        for board in cases:
            result = self.module.validate_storyboard(board, valid_roles())
            self.assertEqual("INVALID", result["validation_status"])
            self.assertIn("BEAT_TIMING_INVALID", {item["code"] for item in result["errors"]})

    def test_reference_identity_is_closed_and_declared(self) -> None:
        board = valid_board()
        board["beats"][0]["reference_ids"].append("UNKNOWN-REF")
        undeclared = self.module.validate_storyboard(board, valid_roles())
        self.assertEqual("INPUT_REQUIRED", undeclared["workflow_state"])
        self.assertIn("REFERENCE_UNDECLARED", {item["code"] for item in undeclared["errors"]})

        roles = valid_roles()
        roles["references"].append(deepcopy(roles["references"][0]))
        duplicate = self.module.validate_storyboard(valid_board(), roles)
        self.assertEqual("INVALID", duplicate["validation_status"])
        self.assertIn("REFERENCE_ID_DUPLICATE", {item["code"] for item in duplicate["errors"]})

    def test_multi_keyframe_requires_three_available_control_frames(self) -> None:
        roles = valid_roles()
        roles["references"] = [
            item for item in roles["references"] if not item["reference_id"].startswith("BOARD-")
        ]
        board = valid_board()
        for beat in board["beats"]:
            beat["reference_ids"] = [item for item in beat["reference_ids"] if not item.startswith("BOARD-")]
        result = self.module.validate_storyboard(board, roles)
        self.assertEqual("INPUT_REQUIRED", result["workflow_state"])
        self.assertIn("CONTROL_REFERENCE_REQUIRED", {item["code"] for item in result["errors"]})

    def test_planned_or_unapproved_control_frame_is_not_ready(self) -> None:
        roles = valid_roles()
        target = next(item for item in roles["references"] if item["reference_id"] == "BOARD-MID")
        target["asset_state"] = "generated_unapproved"
        target["content_sha256"] = "7" * 64
        result = self.module.validate_storyboard(valid_board(), roles)
        self.assertEqual("INPUT_REQUIRED", result["workflow_state"])
        self.assertIn("REFERENCE_ASSET_NOT_READY", {item["code"] for item in result["errors"]})

    def test_approval_cannot_be_inferred_or_mixed_with_draft(self) -> None:
        approved_without_receipt = valid_board("human_approved")
        approved_without_receipt["approval"] = None
        result = self.module.validate_storyboard(approved_without_receipt, valid_roles())
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("APPROVAL_REQUIRED", {item["code"] for item in result["errors"]})

        draft_with_receipt = valid_board()
        draft_with_receipt["approval"] = valid_board("human_approved")["approval"]
        result = self.module.validate_storyboard(draft_with_receipt, valid_roles())
        self.assertIn("DRAFT_APPROVAL_FORBIDDEN", {item["code"] for item in result["errors"]})

    def test_approval_must_bind_the_exact_reference_roles(self) -> None:
        board = valid_board("human_approved")
        board["approval"]["reference_roles_sha256"] = "0" * 64
        result = self.module.validate_storyboard(board, valid_roles())
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("REFERENCE_APPROVAL_DIGEST_MISMATCH", {item["code"] for item in result["errors"]})

    def test_cli_rejects_duplicate_keys_and_noncanonical_arguments_as_json(self) -> None:
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary)
            board_path = root / "board.json"
            roles_path = root / "roles.json"
            board_path.write_text('{"shot_id":"A","shot_id":"B"}', encoding="utf-8")
            roles_path.write_text(json.dumps(valid_roles()), encoding="utf-8")
            duplicate = subprocess.run(
                [sys.executable, str(SCRIPT), "--board", str(board_path), "--references", str(roles_path)],
                capture_output=True,
                check=False,
                text=True,
            )
            usage = subprocess.run(
                [sys.executable, str(SCRIPT), str(board_path), str(roles_path)],
                capture_output=True,
                check=False,
                text=True,
            )
        self.assertEqual(2, duplicate.returncode)
        self.assertEqual("INVALID", json.loads(duplicate.stdout)["validation_status"])
        self.assertEqual("", duplicate.stderr)
        self.assertEqual(2, usage.returncode)
        self.assertEqual("INVALID", json.loads(usage.stdout)["validation_status"])
        self.assertEqual("", usage.stderr)

    def test_public_fixtures_cover_missing_draft_approved_and_reference_conflict(self) -> None:
        roles = json.loads((FIXTURES / "reference-roles-valid.json").read_text(encoding="utf-8"))
        expected = {
            "board-missing-input.json": "INPUT_REQUIRED",
            "board-action-draft.json": "BOARD_DRAFT_READY",
            "board-action-approved.json": None,
        }
        for name, state in expected.items():
            board = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
            result = self.module.validate_storyboard(board, roles)
            self.assertEqual(state, result["workflow_state"], name)
        conflicting_roles = json.loads(
            (FIXTURES / "reference-roles-conflict.json").read_text(encoding="utf-8")
        )
        conflict = self.module.validate_storyboard(
            json.loads((FIXTURES / "board-action-draft.json").read_text(encoding="utf-8")),
            conflicting_roles,
        )
        self.assertEqual("INVALID", conflict["validation_status"])
        self.assertIn("REFERENCE_ID_DUPLICATE", {item["code"] for item in conflict["errors"]})

    def test_public_approved_fixture_binds_public_draft_and_references(self) -> None:
        draft = json.loads((FIXTURES / "board-action-draft.json").read_text(encoding="utf-8"))
        approved = json.loads((FIXTURES / "board-action-approved.json").read_text(encoding="utf-8"))
        roles = json.loads((FIXTURES / "reference-roles-valid.json").read_text(encoding="utf-8"))
        self.assertEqual(canonical_sha256(draft), approved["approval"]["draft_sha256"])
        self.assertEqual(
            canonical_sha256(roles),
            approved["approval"]["reference_roles_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
