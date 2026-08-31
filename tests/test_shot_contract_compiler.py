from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ai-anime-production-director"
COMPILER_PATH = SKILL_ROOT / "scripts" / "compile_shot_contract.py"
FIXTURES = SKILL_ROOT / "fixtures"


def load(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"missing module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ShotContractCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiler = load(COMPILER_PATH, "shot_contract_compiler")
        cls.draft = json.loads((FIXTURES / "board-action-draft.json").read_text(encoding="utf-8"))
        cls.roles = json.loads((FIXTURES / "reference-roles-valid.json").read_text(encoding="utf-8"))

    def approved_pair(self):
        draft = deepcopy(self.draft)
        approved = deepcopy(draft)
        approved["board_state"] = "human_approved"
        approved["approval"] = {
            "approver_id": "synthetic-director",
            "approved_at": "2026-08-30T20:00:00Z",
            "draft_sha256": self.compiler.canonical_sha256(draft),
            "reference_roles_sha256": self.compiler.canonical_sha256(self.roles),
        }
        return draft, approved

    def test_compiles_only_bound_approved_board(self) -> None:
        draft, approved = self.approved_pair()
        contract = self.compiler.compile_contract(draft, approved, deepcopy(self.roles))
        self.assertEqual(self.compiler.canonical_sha256(approved), contract["approved_board_sha256"])
        self.assertEqual(self.compiler.canonical_sha256(self.roles), contract["reference_roles_sha256"])
        self.assertEqual("multi-beat-action-prop-transition", contract["route_class"])
        self.assertEqual("multi-keyframe", contract["control_method"])
        self.assertFalse(contract["generation_authorized"])
        self.assertEqual(draft["beats"], contract["key_beats"])

    def test_rejects_draft_as_approved_input(self) -> None:
        draft = deepcopy(self.draft)
        with self.assertRaisesRegex(self.compiler.CompilationError, "human-approved"):
            self.compiler.compile_contract(draft, deepcopy(draft), deepcopy(self.roles))

    def test_rejects_approval_digest_mismatch(self) -> None:
        draft, approved = self.approved_pair()
        approved["approval"]["draft_sha256"] = "0" * 64
        with self.assertRaisesRegex(self.compiler.CompilationError, "draft digest"):
            self.compiler.compile_contract(draft, approved, deepcopy(self.roles))

    def test_rejects_reference_roles_changed_after_approval(self) -> None:
        draft, approved = self.approved_pair()
        changed_roles = deepcopy(self.roles)
        changed_roles["references"][0]["description"] = "Changed after human approval."
        with self.assertRaisesRegex(self.compiler.CompilationError, "reference-role digest"):
            self.compiler.compile_contract(draft, approved, changed_roles)

    def test_rejects_material_board_divergence_after_approval(self) -> None:
        draft, approved = self.approved_pair()
        approved["beats"][1]["camera_motion"] = "A different camera move."
        approved["approval"]["draft_sha256"] = self.compiler.canonical_sha256(draft)
        with self.assertRaisesRegex(self.compiler.CompilationError, "differs from approved draft"):
            self.compiler.compile_contract(draft, approved, deepcopy(self.roles))

    def test_invalid_cli_input_never_creates_output(self) -> None:
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary)
            draft_path = root / "draft.json"
            approved_path = root / "approved.json"
            roles_path = root / "roles.json"
            output_path = root / "shot-contract.json"
            draft_path.write_text(json.dumps(self.draft), encoding="utf-8")
            approved_path.write_text(json.dumps(self.draft), encoding="utf-8")
            roles_path.write_text(json.dumps(self.roles), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(COMPILER_PATH),
                    "--draft",
                    str(draft_path),
                    "--board",
                    str(approved_path),
                    "--references",
                    str(roles_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(output_path.exists())
        self.assertEqual("", completed.stderr)
        self.assertEqual("INVALID", json.loads(completed.stdout)["validation_status"])


if __name__ == "__main__":
    unittest.main()
