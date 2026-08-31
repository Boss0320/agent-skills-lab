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
SKILL_ROOT = ROOT / "skills" / "dual-lens-investment-review"
DELIVERY_PATH = SKILL_ROOT / "scripts" / "validate_lens_delivery.py"
RECONCILER_PATH = SKILL_ROOT / "scripts" / "reconcile_reviews.py"


def load(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"missing module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence() -> list[dict[str, object]]:
    return [{"path": "report.md", "line": 4, "excerpt": "[C1] Revenue grew 34%."}]


def decision(lens: str = "decision_usability", disposition: str = "PASS") -> dict[str, object]:
    material = disposition == "BLOCK"
    return {
        "case_id": "CASE-SAMPLE",
        "lens": lens,
        "disposition": disposition,
        "material_failure": material,
        "primary_claim_id": None if disposition == "PASS" else "C1",
        "primary_category": None if disposition == "PASS" else ("THESIS" if lens == "decision_usability" else "SOURCE_SUPPORT"),
    }


def review(lens: str = "decision_usability", disposition: str = "PASS") -> dict[str, object]:
    material = disposition == "BLOCK"
    finding = {
        "finding_id": "F-01",
        "severity": "MATERIAL" if material else "MINOR",
        "category": "THESIS" if lens == "decision_usability" else "SOURCE_SUPPORT",
        "claim_ids": ["C1"],
        "summary": "The claim needs correction before this decision.",
        "evidence": evidence(),
    }
    value: dict[str, object] = {
        "case_id": "CASE-SAMPLE",
        "lens": lens,
        "disposition": disposition,
        "material_failure": material,
        "findings": [] if disposition == "PASS" else [finding],
        "residual_risk": "Only supplied synthetic inputs were reviewed.",
    }
    if lens == "source_integrity":
        value["claim_checks"] = [
            {
                "claim_id": "C1",
                "status": "SUPPORTED" if disposition == "PASS" else ("CONTRADICTED" if material else "UNKNOWN"),
                "material": material,
                "source_refs": evidence(),
            }
        ]
    return value


class DualLensDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.delivery = load(DELIVERY_PATH, "dual_lens_delivery")
        cls.reconciler = load(RECONCILER_PATH, "dual_lens_reconciler_for_delivery")

    def test_valid_pair_becomes_available_with_frozen_digests(self) -> None:
        result = self.delivery.validate_delivery(
            decision(),
            review(),
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        self.assertEqual("AVAILABLE", result["execution_state"])
        self.assertEqual({"lens-decision.json", "lens-review.json"}, set(result["files"]))
        self.assertEqual({"lens-decision.json", "lens-review.json"}, set(result["sha256"]))
        self.assertEqual([], result["errors"])

    def test_partial_or_malformed_capture_is_unavailable_without_disposition(self) -> None:
        partial = self.delivery.validate_capture(
            {"files": {"lens-decision.json": decision()}},
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        self.assertEqual("UNAVAILABLE", partial["execution_state"])
        self.assertNotIn("files", partial)
        self.assertNotIn("disposition", partial)
        self.assertNotIn("verdict", partial)

        malformed = self.delivery.validate_capture(
            {"files": {"lens-decision.json": decision(), "lens-review.json": review()}, "extra": True},
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        self.assertEqual("UNAVAILABLE", malformed["execution_state"])

    def test_wrong_case_lens_and_pair_disagreement_are_unavailable(self) -> None:
        wrong_case = decision()
        wrong_case["case_id"] = "CASE-OTHER"
        result = self.delivery.validate_delivery(
            wrong_case,
            review(),
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        codes = {item["code"] for item in result["errors"]}
        self.assertEqual("UNAVAILABLE", result["execution_state"])
        self.assertIn("CASE_ID_MISMATCH", codes)

        disagreement = review(disposition="REVISE")
        result = self.delivery.validate_delivery(
            decision(),
            disagreement,
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        self.assertIn("PAIR_DISAGREEMENT", {item["code"] for item in result["errors"]})

    def test_decision_primary_claim_and_category_must_match_review(self) -> None:
        tiny = decision(disposition="REVISE")
        tiny["primary_claim_id"] = "C9"
        result = self.delivery.validate_delivery(
            tiny,
            review(disposition="REVISE"),
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        self.assertEqual("UNAVAILABLE", result["execution_state"])
        self.assertIn("PRIMARY_FINDING_MISMATCH", {item["code"] for item in result["errors"]})

    def test_oversized_combined_output_is_unavailable(self) -> None:
        result = self.delivery.validate_delivery(
            decision(),
            review(),
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=100,
        )
        self.assertEqual("UNAVAILABLE", result["execution_state"])
        self.assertIn("OUTPUT_TOO_LARGE", {item["code"] for item in result["errors"]})

    def test_unavailable_controller_state_cannot_enter_reconciler(self) -> None:
        unavailable = self.delivery.validate_delivery(
            {},
            review(),
            expected_case_id="CASE-SAMPLE",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        with self.assertRaises(ValueError):
            self.reconciler.reconcile(unavailable, review("source_integrity"))

    def test_cli_capture_and_direct_modes_are_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary)
            capture = root / "capture.json"
            decision_path = root / "lens-decision.json"
            review_path = root / "lens-review.json"
            capture.write_text(json.dumps({"files": {"lens-decision.json": decision(), "lens-review.json": review()}}), encoding="utf-8")
            decision_path.write_text(json.dumps(decision()), encoding="utf-8")
            review_path.write_text(json.dumps(review()), encoding="utf-8")
            valid = subprocess.run(
                [sys.executable, str(DELIVERY_PATH), "--capture", str(capture), "--case", "CASE-SAMPLE", "--lens", "decision_usability", "--max-bytes", "6000"],
                capture_output=True,
                check=False,
                text=True,
            )
            mixed = subprocess.run(
                [sys.executable, str(DELIVERY_PATH), "--capture", str(capture), "--decision", str(decision_path), "--review", str(review_path), "--case", "CASE-SAMPLE", "--lens", "decision_usability", "--max-bytes", "6000"],
                capture_output=True,
                check=False,
                text=True,
            )
        self.assertEqual(0, valid.returncode)
        self.assertEqual("AVAILABLE", json.loads(valid.stdout)["execution_state"])
        self.assertEqual(2, mixed.returncode)
        self.assertEqual("UNAVAILABLE", json.loads(mixed.stdout)["execution_state"])
        self.assertEqual("", mixed.stderr)

    def test_duplicate_json_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            capture = Path(temporary) / "capture.json"
            capture.write_text('{"files":{},"files":{}}', encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(DELIVERY_PATH), "--capture", str(capture), "--case", "CASE-SAMPLE", "--lens", "decision_usability", "--max-bytes", "6000"],
                capture_output=True,
                check=False,
                text=True,
            )
        self.assertEqual(2, completed.returncode)
        self.assertEqual("UNAVAILABLE", json.loads(completed.stdout)["execution_state"])
        self.assertEqual("", completed.stderr)

    def test_direct_mode_rejects_symlinked_artifact(self) -> None:
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary)
            real_decision = root / "real-decision.json"
            linked_decision = root / "lens-decision.json"
            review_path = root / "lens-review.json"
            real_decision.write_text(json.dumps(decision()), encoding="utf-8")
            linked_decision.symlink_to(real_decision)
            review_path.write_text(json.dumps(review()), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(DELIVERY_PATH),
                    "--decision",
                    str(linked_decision),
                    "--review",
                    str(review_path),
                    "--case",
                    "CASE-SAMPLE",
                    "--lens",
                    "decision_usability",
                    "--max-bytes",
                    "6000",
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        self.assertEqual(2, completed.returncode)
        self.assertEqual("UNAVAILABLE", json.loads(completed.stdout)["execution_state"])
        self.assertEqual("", completed.stderr)


if __name__ == "__main__":
    unittest.main()
