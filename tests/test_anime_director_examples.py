from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ai-anime-production-director"
EXAMPLE = SKILL_ROOT / "examples" / "five-second-sword-charge"


def load(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"missing module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnimeDirectorExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        scripts = SKILL_ROOT / "scripts"
        cls.storyboard = load(scripts / "validate_storyboard.py", "example_storyboard_validator")
        cls.compiler = load(scripts / "compile_shot_contract.py", "example_contract_compiler")
        cls.contract_validator = load(scripts / "validate_shot_contract.py", "example_contract_validator")

    def read_json(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def test_example_has_draft_and_explicit_approved_stages(self) -> None:
        required = (
            "brief.md",
            "draft/shot-board.json",
            "draft/shot-board.md",
            "draft/reference-roles.json",
            "approved/human-approval.json",
            "approved/shot-board.json",
            "approved/shot-board.md",
            "approved/reference-roles.json",
            "approved/shot-contract.json",
            "approved/generation-handoff.md",
        )
        for relative in required:
            self.assertTrue((EXAMPLE / relative).is_file(), relative)

    def test_draft_is_not_ready_and_approved_stage_is_digest_bound(self) -> None:
        draft = self.read_json(EXAMPLE / "draft" / "shot-board.json")
        draft_roles = self.read_json(EXAMPLE / "draft" / "reference-roles.json")
        draft_result = self.storyboard.validate_storyboard(draft, draft_roles)
        self.assertEqual("BOARD_DRAFT_READY", draft_result["workflow_state"])

        approved = self.read_json(EXAMPLE / "approved" / "shot-board.json")
        approved_roles = self.read_json(EXAMPLE / "approved" / "reference-roles.json")
        receipt = self.read_json(EXAMPLE / "approved" / "human-approval.json")
        self.assertEqual(receipt, approved["approval"])
        self.assertEqual(self.compiler.canonical_sha256(draft), receipt["draft_sha256"])
        self.assertEqual("compile_shot_contract", self.storyboard.validate_storyboard(approved, approved_roles)["next_action"])

    def test_committed_contract_equals_compiler_and_is_motion_proof_ready(self) -> None:
        draft = self.read_json(EXAMPLE / "draft" / "shot-board.json")
        approved = self.read_json(EXAMPLE / "approved" / "shot-board.json")
        roles = self.read_json(EXAMPLE / "approved" / "reference-roles.json")
        expected = self.compiler.compile_contract(draft, approved, roles)
        committed = self.read_json(EXAMPLE / "approved" / "shot-contract.json")
        self.assertEqual(expected, committed)
        result = self.contract_validator.validate_contract(committed, approved, roles)
        self.assertEqual("MOTION_PROOF_READY", result["workflow_state"])
        self.assertFalse(committed["generation_authorized"])

    def test_handoff_is_plain_language_and_does_not_grant_generation(self) -> None:
        handoff = (EXAMPLE / "approved" / "generation-handoff.md").read_text(encoding="utf-8")
        for heading in ("## Outcome", "## Why", "## Next safe action", "## Not proven"):
            self.assertIn(heading, handoff)
        self.assertIn("MOTION_PROOF_READY", handoff)
        self.assertIn("separate authorization", handoff)
        self.assertNotIn("generation is authorized", handoff.casefold())
        self.assertNotIn("buy credits", handoff.casefold())


if __name__ == "__main__":
    unittest.main()
