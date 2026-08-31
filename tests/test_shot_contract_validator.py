from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ai-anime-production-director"
COMPILER_PATH = SKILL_ROOT / "scripts" / "compile_shot_contract.py"
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_shot_contract.py"
FIXTURES = SKILL_ROOT / "fixtures"


def load(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"missing module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ShotContractValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiler = load(COMPILER_PATH, "shot_contract_compiler_for_validator")
        cls.validator = load(VALIDATOR_PATH, "shot_contract_validator_v2")
        cls.draft = json.loads((FIXTURES / "board-action-draft.json").read_text(encoding="utf-8"))
        cls.roles = json.loads((FIXTURES / "reference-roles-valid.json").read_text(encoding="utf-8"))

    def contract(self):
        draft = deepcopy(self.draft)
        approved = deepcopy(draft)
        approved["board_state"] = "human_approved"
        approved["approval"] = {
            "approver_id": "synthetic-director",
            "approved_at": "2026-08-30T20:00:00Z",
            "draft_sha256": self.compiler.canonical_sha256(draft),
            "reference_roles_sha256": self.compiler.canonical_sha256(self.roles),
        }
        return self.compiler.compile_contract(draft, approved, deepcopy(self.roles)), approved

    def test_valid_contract_is_motion_proof_ready(self) -> None:
        contract, approved = self.contract()
        result = self.validator.validate_contract(contract, approved, self.roles)
        self.assertEqual("VALID", result["validation_status"])
        self.assertEqual("MOTION_PROOF_READY", result["workflow_state"])
        self.assertEqual("request_separate_motion_proof_authorization", result["next_action"])

    def test_unresolved_prop_boundary_is_input_required(self) -> None:
        contract, _ = self.contract()
        contract["prop_state"]["end"] = None
        result = self.validator.validate_contract(contract)
        self.assertEqual("INPUT_REQUIRED", result["workflow_state"])
        self.assertIn("PROP_END_STATE_REQUIRED", {item["code"] for item in result["errors"]})

    def test_adjacent_direction_conflict_requires_sequence_review(self) -> None:
        contract, _ = self.contract()
        contract["adjacent_shots"]["previous_screen_direction"] = "right-to-left"
        result = self.validator.validate_contract(contract)
        self.assertEqual("SEQUENCE_REVIEW_REQUIRED", result["workflow_state"])

    def test_incompatible_control_method_requires_redesign(self) -> None:
        contract, _ = self.contract()
        contract["control_method"] = "single-keyframe"
        result = self.validator.validate_contract(contract)
        self.assertEqual("SHOT_REDESIGN_REQUIRED", result["workflow_state"])
        self.assertIn("CONTROL_METHOD_INCOMPATIBLE", {item["code"] for item in result["errors"]})

    def test_extra_keys_and_generation_authority_fail_closed(self) -> None:
        contract, _ = self.contract()
        contract["provider"] = "invented-provider"
        result = self.validator.validate_contract(contract)
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("CONTRACT_KEYS_INVALID", {item["code"] for item in result["errors"]})

        contract, _ = self.contract()
        contract["generation_authorized"] = True
        result = self.validator.validate_contract(contract)
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("GENERATION_AUTHORITY_INVALID", {item["code"] for item in result["errors"]})

    def test_source_digest_mismatch_is_invalid(self) -> None:
        contract, approved = self.contract()
        changed = deepcopy(approved)
        changed["story_function"] = "Changed after contract compilation."
        result = self.validator.validate_contract(contract, changed, self.roles)
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("BOARD_DIGEST_MISMATCH", {item["code"] for item in result["errors"]})

    def test_ready_state_requires_bound_source_artifacts(self) -> None:
        contract, _ = self.contract()
        result = self.validator.validate_contract(contract)
        self.assertEqual("INPUT_REQUIRED", result["workflow_state"])
        self.assertIn("SOURCE_ARTIFACTS_REQUIRED", {item["code"] for item in result["errors"]})

    def test_contract_field_drift_from_bound_board_is_invalid(self) -> None:
        contract, approved = self.contract()
        contract["control_method"] = "single-keyframe"
        result = self.validator.validate_contract(contract, approved, self.roles)
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("CONTRACT_BOARD_PARITY_MISMATCH", {item["code"] for item in result["errors"]})

    def test_invalid_approved_board_cannot_back_a_valid_contract(self) -> None:
        contract, approved = self.contract()
        changed = deepcopy(approved)
        changed["secret_shortcut"] = True
        contract["approved_board_sha256"] = self.validator.canonical_sha256(changed)
        result = self.validator.validate_contract(contract, changed, self.roles)
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("SOURCE_BOARD_INVALID", {item["code"] for item in result["errors"]})

    def test_approval_timestamp_requires_timezone(self) -> None:
        contract, _ = self.contract()
        contract["approval"]["approved_at"] = "sometime"
        result = self.validator.validate_contract(contract)
        self.assertEqual("INVALID", result["validation_status"])
        self.assertIn("APPROVAL_INVALID", {item["code"] for item in result["errors"]})

    def test_retired_states_are_never_emitted(self) -> None:
        contract, _ = self.contract()
        result = self.validator.validate_contract(contract)
        self.assertNotIn(result["workflow_state"], {"BLOCKED", "RETAKE", "SEQUENCE REVIEW READY"})
        self.assertIn(
            result["workflow_state"],
            {"INPUT_REQUIRED", "SEQUENCE_REVIEW_REQUIRED", "SHOT_REDESIGN_REQUIRED", "MOTION_PROOF_READY"},
        )


if __name__ == "__main__":
    unittest.main()
