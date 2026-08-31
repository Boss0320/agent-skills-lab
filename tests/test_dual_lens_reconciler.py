from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/dual-lens-investment-review/scripts/reconcile_reviews.py"


def load_module():
    spec = importlib.util.spec_from_file_location("dual_lens_reconciler", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load reconciler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence() -> list[dict[str, object]]:
    return [{"path": "report.md", "line": 4, "excerpt": "[C1] Revenue grew 34%."}]


def finding(lens: str, material: bool = True) -> dict[str, object]:
    return {
        "finding_id": "F-01",
        "severity": "MATERIAL" if material else "MINOR",
        "category": "SOURCE_SUPPORT" if lens == "source_integrity" else "THESIS",
        "claim_ids": ["C1"],
        "summary": "The claim cannot support the stated decision.",
        "evidence": evidence(),
    }


def usability(disposition: str = "PASS", material: bool = False) -> dict[str, object]:
    return {
        "case_id": "CASE-SAMPLE",
        "lens": "decision_usability",
        "disposition": disposition,
        "material_failure": material,
        "findings": [] if disposition == "PASS" else [finding("decision_usability", material)],
        "residual_risk": "Source support is outside this lens.",
    }


def integrity(disposition: str = "PASS", material: bool = False) -> dict[str, object]:
    return {
        "case_id": "CASE-SAMPLE",
        "lens": "source_integrity",
        "disposition": disposition,
        "material_failure": material,
        "claim_checks": [
            {
                "claim_id": "C1",
                "status": "SUPPORTED" if disposition == "PASS" else "CONTRADICTED",
                "material": material,
                "source_refs": evidence(),
            }
        ],
        "findings": [] if disposition == "PASS" else [finding("source_integrity", material)],
        "residual_risk": "Only supplied synthetic sources were checked.",
    }


class ReconcilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_source_integrity_material_failure_is_hard_veto(self) -> None:
        result = self.module.reconcile(usability(), integrity("BLOCK", True))
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertEqual(result["veto_source"], "source_integrity")

    def test_decision_usability_material_failure_can_block(self) -> None:
        result = self.module.reconcile(usability("BLOCK", True), integrity())
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertEqual(result["veto_source"], "decision_usability")

    def test_non_material_revision_propagates_without_block(self) -> None:
        result = self.module.reconcile(usability(), integrity("REVISE", False))
        self.assertEqual(result["verdict"], "REVISE")
        self.assertEqual(result["veto_source"], "none")

    def test_two_passing_lenses_are_ready_for_human_review(self) -> None:
        result = self.module.reconcile(usability(), integrity())
        self.assertEqual(result["verdict"], "READY_FOR_HUMAN_REVIEW")
        self.assertEqual(result["veto_source"], "none")

    def test_extra_key_and_case_mismatch_fail_closed(self) -> None:
        extra = usability()
        extra["expected_verdict"] = "BLOCK"
        with self.assertRaisesRegex(ValueError, "decision_usability"):
            self.module.reconcile(extra, integrity())
        mismatch = integrity()
        mismatch["case_id"] = "CASE-OTHER"
        with self.assertRaisesRegex(ValueError, "case_id"):
            self.module.reconcile(usability(), mismatch)

    def test_passing_integrity_cannot_hide_material_contradicted_claim(self) -> None:
        inconsistent = integrity()
        inconsistent["claim_checks"][0]["status"] = "CONTRADICTED"
        inconsistent["claim_checks"][0]["material"] = True
        with self.assertRaisesRegex(ValueError, "claim_checks relationship"):
            self.module.reconcile(usability(), inconsistent)

    def test_reviewer_digests_are_deterministic_and_input_sensitive(self) -> None:
        first = self.module.reconcile(usability(), integrity())
        second = self.module.reconcile(deepcopy(usability()), deepcopy(integrity()))
        changed_integrity = integrity()
        changed_integrity["residual_risk"] = "Different residual risk."
        changed = self.module.reconcile(usability(), changed_integrity)
        self.assertEqual(first["reviewer_digests"], second["reviewer_digests"])
        self.assertNotEqual(
            first["reviewer_digests"]["source_integrity"],
            changed["reviewer_digests"]["source_integrity"],
        )


if __name__ == "__main__":
    unittest.main()
