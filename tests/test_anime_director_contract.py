from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ai-anime-production-director"


class AnimeDirectorContractTests(unittest.TestCase):
    def text(self, relative: str) -> str:
        return (SKILL_ROOT / relative).read_text(encoding="utf-8")

    def test_frontmatter_and_main_skill_size_are_closed(self) -> None:
        text = self.text("SKILL.md")
        self.assertTrue(text.startswith("---\nname: ai-anime-production-director\n"))
        self.assertIn("description:", text.split("---", 2)[1])
        self.assertLess(len(text.splitlines()), 500)

    def test_skill_names_both_storyboard_outputs_and_reference_roles(self) -> None:
        text = self.text("SKILL.md")
        for phrase in (
            "shot-board.json",
            "shot-board.md",
            "reference-roles.json",
            "shot-contract.json",
            "generation-handoff.md",
        ):
            self.assertIn(phrase, text)

    def test_skill_requires_explicit_human_approval_before_contract(self) -> None:
        text = self.text("SKILL.md")
        self.assertIn("human_approved", text)
        self.assertIn("Silence is not approval", text)
        approval_position = text.index("human_approved")
        contract_position = text.index("shot-contract.json")
        self.assertLess(approval_position, contract_position)

    def test_skill_declares_the_five_closed_workflow_states(self) -> None:
        text = self.text("SKILL.md")
        for state in (
            "INPUT_REQUIRED",
            "BOARD_DRAFT_READY",
            "SEQUENCE_REVIEW_REQUIRED",
            "SHOT_REDESIGN_REQUIRED",
            "MOTION_PROOF_READY",
        ):
            self.assertIn(state, text)


if __name__ == "__main__":
    unittest.main()
