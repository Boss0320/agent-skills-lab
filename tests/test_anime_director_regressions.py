from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "ai-anime-production-director"


class AnimeDirectorRegressionTests(unittest.TestCase):
    def corpus(self) -> str:
        paths = (
            SKILL_ROOT / "SKILL.md",
            SKILL_ROOT / "references" / "shot-contract.md",
            SKILL_ROOT / "scripts" / "validate_shot_contract.py",
        )
        return "\n".join(path.read_text(encoding="utf-8") for path in paths)

    def test_retired_ambiguous_state_is_absent(self) -> None:
        self.assertNotIn("SEQUENCE REVIEW READY", self.corpus())

    def test_silence_cannot_authorize_invented_staging(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "make explicit creative staging choices when a brief is merely silent",
            text,
        )
        self.assertIn("label it `proposed`", text)

    def test_skill_never_auto_generates_or_selects_a_provider(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_boundaries = (
            "Do not automatically generate images or video",
            "Do not select a provider",
            "Do not authorize spend",
        )
        for boundary in required_boundaries:
            self.assertIn(boundary, text)

    def test_motion_proof_readiness_does_not_claim_visual_quality(self) -> None:
        text = self.corpus().casefold()
        for unsupported in (
            "guarantees visual quality",
            "proves finished video quality",
            "guarantees good animation",
        ):
            self.assertNotIn(unsupported, text)
        self.assertIn("does not prove", text)


if __name__ == "__main__":
    unittest.main()
