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


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence() -> list[dict[str, object]]:
    return [{"path": "report.md", "line": 7, "excerpt": "[C1] Revenue grew 14%."}]


def usability() -> dict[str, object]:
    return {
        "case_id": "CASE-GUIDED",
        "lens": "decision_usability",
        "disposition": "PASS",
        "material_failure": False,
        "findings": [],
        "residual_risk": "Source support remains outside this lens.",
    }


def integrity(status: str, material: bool) -> dict[str, object]:
    disposition = "PASS" if status == "SUPPORTED" else ("BLOCK" if material else "REVISE")
    return {
        "case_id": "CASE-GUIDED",
        "lens": "source_integrity",
        "disposition": disposition,
        "material_failure": material,
        "findings": []
        if disposition == "PASS"
        else [
            {
                "finding_id": "I-01",
                "severity": "MATERIAL" if material else "MINOR",
                "category": "SOURCE_SUPPORT",
                "claim_ids": ["C1"],
                "summary": "The supplied packet does not establish this claim.",
                "evidence": evidence(),
            }
        ],
        "claim_checks": [
            {
                "claim_id": "C1",
                "status": status,
                "material": material,
                "source_refs": evidence(),
            }
        ],
        "residual_risk": "Only the frozen packet was checked.",
    }


def decision(review: dict[str, object]) -> dict[str, object]:
    finding = review["findings"][0] if review["findings"] else None
    return {
        "case_id": review["case_id"],
        "lens": review["lens"],
        "disposition": review["disposition"],
        "material_failure": review["material_failure"],
        "primary_claim_id": None if finding is None else finding["claim_ids"][0],
        "primary_category": None if finding is None else finding["category"],
    }


class DualLensMaterialityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reconciler = load(
            SKILL_ROOT / "scripts" / "reconcile_reviews.py",
            "dual_lens_materiality_reconciler",
        )
        cls.delivery = load(
            SKILL_ROOT / "scripts" / "validate_lens_delivery.py",
            "dual_lens_materiality_delivery",
        )

    def test_skill_exposes_guided_and_expert_modes(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        guide = (SKILL_ROOT / "references" / "guided-intake-and-materiality.md").read_text(encoding="utf-8")
        self.assertIn("Guided mode", skill)
        self.assertIn("Expert mode", skill)
        self.assertIn("decision consequence", guide)
        self.assertIn("polish-only", guide)
        self.assertIn("UNKNOWN", guide)

    def test_non_material_unknown_revises_but_does_not_block(self) -> None:
        review = integrity("UNKNOWN", False)
        self.assertEqual([], self.reconciler.validate_review(review, "source_integrity"))
        result = self.reconciler.reconcile(usability(), review)
        self.assertEqual("REVISE", result["verdict"])

    def test_material_contradiction_blocks(self) -> None:
        result = self.reconciler.reconcile(usability(), integrity("CONTRADICTED", True))
        self.assertEqual("BLOCK", result["verdict"])
        self.assertEqual("source_integrity", result["veto_source"])

    def test_material_finding_cannot_point_to_supported_or_unrelated_claim(self) -> None:
        inconsistent = integrity("SUPPORTED", False)
        inconsistent["disposition"] = "BLOCK"
        inconsistent["material_failure"] = True
        inconsistent["findings"] = integrity("CONTRADICTED", True)["findings"]
        self.assertTrue(self.reconciler.validate_review(inconsistent, "source_integrity"))

        unrelated = integrity("CONTRADICTED", True)
        unrelated["findings"][0]["claim_ids"] = ["C9"]
        self.assertTrue(self.reconciler.validate_review(unrelated, "source_integrity"))

    def test_reconciliation_requires_two_available_untampered_deliveries(self) -> None:
        usability_review = usability()
        integrity_review = integrity("SUPPORTED", False)
        usability_delivery = self.delivery.validate_delivery(
            decision(usability_review),
            usability_review,
            expected_case_id="CASE-GUIDED",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        integrity_delivery = self.delivery.validate_delivery(
            decision(integrity_review),
            integrity_review,
            expected_case_id="CASE-GUIDED",
            expected_lens="source_integrity",
            max_bytes=6000,
        )
        result = self.reconciler.reconcile_available_deliveries(
            usability_delivery,
            integrity_delivery,
        )
        self.assertEqual("READY_FOR_HUMAN_REVIEW", result["verdict"])

        unavailable = deepcopy(usability_delivery)
        unavailable["execution_state"] = "UNAVAILABLE"
        with self.assertRaisesRegex(ValueError, "AVAILABLE"):
            self.reconciler.reconcile_available_deliveries(unavailable, integrity_delivery)

        tampered = deepcopy(integrity_delivery)
        tampered["files"]["lens-review.json"]["residual_risk"] = "Changed after validation."
        with self.assertRaisesRegex(ValueError, "digest"):
            self.reconciler.reconcile_available_deliveries(usability_delivery, tampered)

        forged_size = deepcopy(integrity_delivery)
        forged_size["combined_bytes"] = 1
        with self.assertRaisesRegex(ValueError, "byte"):
            self.reconciler.reconcile_available_deliveries(usability_delivery, forged_size)

    def test_reconciler_cli_rejects_duplicate_keys_and_preserves_existing_output(self) -> None:
        usability_review = usability()
        integrity_review = integrity("SUPPORTED", False)
        usability_delivery = self.delivery.validate_delivery(
            decision(usability_review),
            usability_review,
            expected_case_id="CASE-GUIDED",
            expected_lens="decision_usability",
            max_bytes=6000,
        )
        integrity_delivery = self.delivery.validate_delivery(
            decision(integrity_review),
            integrity_review,
            expected_case_id="CASE-GUIDED",
            expected_lens="source_integrity",
            max_bytes=6000,
        )
        script = SKILL_ROOT / "scripts" / "reconcile_reviews.py"
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary)
            usability_path = root / "usability.json"
            integrity_path = root / "integrity.json"
            output_path = root / "result.json"
            usability_path.write_text('{"files":{},"files":{}}', encoding="utf-8")
            integrity_path.write_text(json.dumps(integrity_delivery), encoding="utf-8")
            duplicate = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--usability-delivery",
                    str(usability_path),
                    "--integrity-delivery",
                    str(integrity_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(1, duplicate.returncode)
            self.assertFalse(output_path.exists())

            usability_path.write_text(json.dumps(usability_delivery), encoding="utf-8")
            output_path.write_text("preserve-me\n", encoding="utf-8")
            existing = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--usability-delivery",
                    str(usability_path),
                    "--integrity-delivery",
                    str(integrity_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(1, existing.returncode)
            self.assertEqual("preserve-me\n", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
