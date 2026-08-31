from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_detection_record_validator import materialize_root, record
from tests.test_dual_lens_delivery import decision, review


ROOT = Path(__file__).resolve().parents[1]
A_ROOT = ROOT / "skills" / "agent-system-integration-audit"
B_ROOT = ROOT / "skills" / "dual-lens-investment-review"
C_ROOT = ROOT / "skills" / "ai-anime-production-director"


def run(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *(str(item) for item in arguments)],
        capture_output=True,
        check=False,
        text=True,
    )


class PublicValidatorMatrixTests(unittest.TestCase):
    def test_a_validators_cover_bound_detection_clean_packet_and_malformed_transport(self) -> None:
        detection_script = A_ROOT / "scripts" / "validate_detection_record.py"
        packet_script = A_ROOT / "scripts" / "validate_audit_packet.py"
        catalog = A_ROOT / "fixtures" / "catalog.json"
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            temp = Path(temporary)
            project = temp / "project"
            project.mkdir()
            value = record()
            materialize_root(project, value)
            detection = temp / "detection.json"
            detection.write_text(json.dumps(value), encoding="utf-8")
            valid_detection = run(
                detection_script,
                "--input",
                detection,
                "--root",
                project,
                "--max-bytes",
                12000,
            )
            self.assertEqual(0, valid_detection.returncode)
            self.assertTrue(json.loads(valid_detection.stdout)["valid"])

            malformed_detection = temp / "malformed-detection.json"
            malformed_detection.write_text('{"scope":"a","scope":"b"}', encoding="utf-8")
            malformed = run(
                detection_script,
                "--input",
                malformed_detection,
                "--root",
                project,
                "--max-bytes",
                12000,
            )
            self.assertEqual(2, malformed.returncode)
            self.assertFalse(json.loads(malformed.stdout)["valid"])

            clean_packet = temp / "clean-packet.json"
            clean_packet.write_text(
                json.dumps(
                    {
                        "status": "CLEAN_CONTROL_PASS",
                        "findings": [],
                        "scope": "CLEAN-03",
                        "residual_risk": "Only the frozen SableFallback route was assessed.",
                    }
                ),
                encoding="utf-8",
            )
            valid_packet = run(
                packet_script,
                "--packet",
                clean_packet,
                "--catalog",
                catalog,
                "--case",
                "CLEAN-03",
            )
            self.assertEqual(0, valid_packet.returncode)
            self.assertEqual({"status": "valid"}, json.loads(valid_packet.stdout))

            malformed_packet = temp / "malformed-packet.json"
            malformed_packet.write_text('{"status":"x","status":"y"}', encoding="utf-8")
            malformed = run(
                packet_script,
                "--packet",
                malformed_packet,
                "--catalog",
                catalog,
                "--case",
                "CLEAN-03",
            )
            self.assertEqual(2, malformed.returncode)
            self.assertIn("errors", json.loads(malformed.stdout))

    def test_b_validators_cover_available_block_unavailable_and_malformed(self) -> None:
        delivery_script = B_ROOT / "scripts" / "validate_lens_delivery.py"
        reconciler_script = B_ROOT / "scripts" / "reconcile_reviews.py"

        def capture(temp: Path, lens: str, disposition: str) -> dict[str, object]:
            path = temp / f"{lens}-{disposition}.json"
            path.write_text(
                json.dumps(
                    {
                        "files": {
                            "lens-decision.json": decision(lens, disposition),
                            "lens-review.json": review(lens, disposition),
                        }
                    }
                ),
                encoding="utf-8",
            )
            completed = run(
                delivery_script,
                "--capture",
                path,
                "--case",
                "CASE-SAMPLE",
                "--lens",
                lens,
                "--max-bytes",
                6000,
            )
            self.assertEqual(0, completed.returncode, completed.stdout)
            return json.loads(completed.stdout)

        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            temp = Path(temporary)
            usability = capture(temp, "decision_usability", "PASS")
            integrity = capture(temp, "source_integrity", "BLOCK")
            usability_path = temp / "usability-delivery.json"
            integrity_path = temp / "integrity-delivery.json"
            usability_path.write_text(json.dumps(usability), encoding="utf-8")
            integrity_path.write_text(json.dumps(integrity), encoding="utf-8")
            result_path = temp / "reconciled.json"
            blocked = run(
                reconciler_script,
                "--usability-delivery",
                usability_path,
                "--integrity-delivery",
                integrity_path,
                "--output",
                result_path,
            )
            self.assertEqual(0, blocked.returncode, blocked.stdout)
            self.assertEqual("BLOCK", json.loads(result_path.read_text(encoding="utf-8"))["verdict"])

            unavailable = deepcopy(usability)
            unavailable["execution_state"] = "UNAVAILABLE"
            unavailable_path = temp / "unavailable.json"
            unavailable_path.write_text(json.dumps(unavailable), encoding="utf-8")
            unavailable_output = temp / "unavailable-result.json"
            rejected = run(
                reconciler_script,
                "--usability-delivery",
                unavailable_path,
                "--integrity-delivery",
                integrity_path,
                "--output",
                unavailable_output,
            )
            self.assertEqual(1, rejected.returncode)
            self.assertFalse(unavailable_output.exists())

            disagreement = temp / "disagreement.json"
            disagreement.write_text(
                json.dumps(
                    {
                        "files": {
                            "lens-decision.json": decision(),
                            "lens-review.json": review(disposition="REVISE"),
                        }
                    }
                ),
                encoding="utf-8",
            )
            contradicted = run(
                delivery_script,
                "--capture",
                disagreement,
                "--case",
                "CASE-SAMPLE",
                "--lens",
                "decision_usability",
                "--max-bytes",
                6000,
            )
            self.assertEqual(1, contradicted.returncode)
            self.assertEqual("UNAVAILABLE", json.loads(contradicted.stdout)["execution_state"])

            malformed_capture = temp / "malformed-capture.json"
            malformed_capture.write_text('{"files":{},"files":{}}', encoding="utf-8")
            malformed = run(
                delivery_script,
                "--capture",
                malformed_capture,
                "--case",
                "CASE-SAMPLE",
                "--lens",
                "decision_usability",
                "--max-bytes",
                6000,
            )
            self.assertEqual(2, malformed.returncode)

    def test_c_validators_cover_draft_approved_conflict_compile_ready_and_malformed(self) -> None:
        storyboard_script = C_ROOT / "scripts" / "validate_storyboard.py"
        compiler_script = C_ROOT / "scripts" / "compile_shot_contract.py"
        contract_script = C_ROOT / "scripts" / "validate_shot_contract.py"
        fixtures = C_ROOT / "fixtures"
        example = C_ROOT / "examples" / "five-second-sword-charge"
        valid_references = fixtures / "reference-roles-valid.json"

        draft = run(
            storyboard_script,
            "--board",
            fixtures / "board-action-draft.json",
            "--references",
            valid_references,
        )
        self.assertEqual(1, draft.returncode)
        self.assertEqual("BOARD_DRAFT_READY", json.loads(draft.stdout)["workflow_state"])

        approved = run(
            storyboard_script,
            "--board",
            fixtures / "board-action-approved.json",
            "--references",
            valid_references,
        )
        self.assertEqual(0, approved.returncode)

        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            temp = Path(temporary)
            conflict_board = json.loads((fixtures / "board-action-draft.json").read_text(encoding="utf-8"))
            conflict_board["adjacent_shots"]["previous_screen_direction"] = "right-to-left"
            conflict_path = temp / "conflict-board.json"
            conflict_path.write_text(json.dumps(conflict_board), encoding="utf-8")
            conflict = run(
                storyboard_script,
                "--board",
                conflict_path,
                "--references",
                valid_references,
            )
            self.assertEqual(1, conflict.returncode)
            self.assertEqual("SEQUENCE_REVIEW_REQUIRED", json.loads(conflict.stdout)["workflow_state"])

            malformed_board = temp / "malformed-board.json"
            malformed_board.write_text('{"shot_id":"a","shot_id":"b"}', encoding="utf-8")
            malformed = run(
                storyboard_script,
                "--board",
                malformed_board,
                "--references",
                valid_references,
            )
            self.assertEqual(2, malformed.returncode)

            compiled_path = temp / "shot-contract.json"
            compiled = run(
                compiler_script,
                "--draft",
                example / "draft" / "shot-board.json",
                "--board",
                example / "approved" / "shot-board.json",
                "--references",
                example / "approved" / "reference-roles.json",
                "--output",
                compiled_path,
            )
            self.assertEqual(0, compiled.returncode, compiled.stdout)
            self.assertTrue(compiled_path.is_file())

            ready = run(
                contract_script,
                "--contract",
                compiled_path,
                "--board",
                example / "approved" / "shot-board.json",
                "--references",
                example / "approved" / "reference-roles.json",
            )
            self.assertEqual(0, ready.returncode)
            self.assertEqual("MOTION_PROOF_READY", json.loads(ready.stdout)["workflow_state"])

            malformed_contract = temp / "malformed-contract.json"
            malformed_contract.write_text('{"shot_id":"a","shot_id":"b"}', encoding="utf-8")
            malformed = run(
                contract_script,
                "--contract",
                malformed_contract,
                "--board",
                example / "approved" / "shot-board.json",
                "--references",
                example / "approved" / "reference-roles.json",
            )
            self.assertEqual(2, malformed.returncode)


if __name__ == "__main__":
    unittest.main()
