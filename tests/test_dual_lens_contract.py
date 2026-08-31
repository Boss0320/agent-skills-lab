from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/dual-lens-investment-review"


class DualLensContractTests(unittest.TestCase):
    def test_skill_frontmatter_and_size_are_closed(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: dual-lens-investment-review\n"))
        self.assertIn("description:", text.split("---", 2)[1])
        self.assertLess(len(text.splitlines()), 500)

    def test_skill_requires_real_context_isolation_and_deterministic_reconciliation(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required = (
            "decision_usability",
            "source_integrity",
            "must not receive",
            "lens-decision.json",
            "lens-review.json",
            "reconcile_reviews.py",
            "READY_FOR_HUMAN_REVIEW",
        )
        for phrase in required:
            self.assertIn(phrase, text)

    def test_contract_preserves_unknown_and_source_veto(self) -> None:
        text = (SKILL_ROOT / "references/review-contract.md").read_text(encoding="utf-8")
        self.assertIn("Unknown is not zero", text)
        self.assertIn("material source-integrity failure", text)
        self.assertIn("hard veto", text)
        self.assertIn("human", text.casefold())

    def test_skill_does_not_claim_investment_performance(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").casefold()
        for forbidden in ("guaranteed return", "proven alpha", "automatic trading"):
            self.assertNotIn(forbidden, text)

    def test_skill_declares_one_sink_and_unavailable_is_not_a_disposition(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        contract = (SKILL_ROOT / "references/review-contract.md").read_text(encoding="utf-8")
        self.assertIn("controller-capture", text)
        self.assertIn("direct file", text)
        self.assertIn("validate_lens_delivery.py", text)
        self.assertIn("UNAVAILABLE", text)
        self.assertIn("UNAVAILABLE is not a lens disposition", contract)


if __name__ == "__main__":
    unittest.main()
