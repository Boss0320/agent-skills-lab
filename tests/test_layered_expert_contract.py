from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "A": ROOT / "skills" / "agent-system-integration-audit",
    "B": ROOT / "skills" / "dual-lens-investment-review",
    "C": ROOT / "skills" / "ai-anime-production-director",
}
HEX64 = re.compile(r"[0-9a-f]{64}")


class LayeredExpertContractTests(unittest.TestCase):
    def test_every_skill_has_one_concise_trigger_and_shared_six_layer_shape(self) -> None:
        for label, root in SKILLS.items():
            text = (root / "SKILL.md").read_text(encoding="utf-8")
            self.assertLess(len(text.splitlines()), 500, label)
            frontmatter = text.split("---", 2)[1]
            self.assertEqual(1, frontmatter.count("name:"), label)
            self.assertEqual(1, frontmatter.count("description:"), label)
            self.assertLess(len(frontmatter), 700, label)
            for term in (
                "Guided mode",
                "Expert mode",
                "Outcome",
                "Why",
                "Next safe action",
                "Not proven",
            ):
                self.assertIn(term, text, f"{label}:{term}")
            self.assertRegex(text, r"scripts/[a-z0-9._/-]+\.py", label)
            self.assertRegex(text, r"(?:JSON|\.json)", label)
            self.assertRegex(text, r"(?:Markdown|\.md)", label)

    def test_every_referenced_public_contract_or_script_exists(self) -> None:
        pattern = re.compile(r"(?:references|scripts)/[a-z0-9._/-]+\.(?:md|py)")
        for label, root in SKILLS.items():
            text = (root / "SKILL.md").read_text(encoding="utf-8")
            references = set(pattern.findall(text))
            self.assertTrue(references, label)
            for relative in references:
                self.assertTrue((root / relative).is_file(), f"{label}:{relative}")
                self.assertFalse((root / relative).is_symlink(), f"{label}:{relative}")

    def test_guided_interface_never_expands_domain_authority(self) -> None:
        a = (SKILLS["A"] / "SKILL.md").read_text(encoding="utf-8")
        b = (SKILLS["B"] / "SKILL.md").read_text(encoding="utf-8")
        c = (SKILLS["C"] / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("read-only", a)
        self.assertIn("does not grant approval", a)
        self.assertIn("not approval to trade", b)
        self.assertIn("Do not fetch missing sources", b)
        self.assertIn("Do not automatically generate images or video", c)
        self.assertIn("Do not authorize spend", c)

    def test_bilingual_readmes_state_verified_behavior_and_bounded_lift(self) -> None:
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        for term in ("0/3 → 2/3", "3/3 → 3/3", "0/6 → 6/6", "0/3 → 3/3", "0/2 → 2/2"):
            self.assertIn(term, en)
            self.assertIn(term, zh)
        for term in (
            "Raw reasoning lift was not scored",
            "Finished-media quality remains unproven",
        ):
            self.assertIn(term, en)
        for term in ("沒有評分自由推理能力是否提升", "尚未證明最終成片品質"):
            self.assertIn(term, zh)
        self.assertIn("dated repository and publication state", en)
        self.assertIn("帶日期的 repo 與公開狀態", zh)
        self.assertIn("PUBLICATION_STATUS.md", en)
        self.assertIn("PUBLICATION_STATUS.md", zh)
        self.assertNotIn("NOT " + "PUBLIC", en)
        self.assertNotIn("尚未" + "公開", zh)

    def test_public_provenance_is_sanitized_and_tracks_three_skill_baselines(self) -> None:
        path = ROOT / "provenance" / "revision-provenance.json"
        provenance = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            {"schema_version", "revision", "state", "repository", "evidence", "rights", "entries"},
            set(provenance),
        )
        self.assertEqual("agent-skills-lab-revision-provenance/v3", provenance["schema_version"])
        self.assertEqual("LOCAL_CANDIDATE_RIGHTS_APPROVED", provenance["state"])
        self.assertEqual("agent-skills-lab", provenance["repository"]["approved_slug"])
        entries = provenance["entries"]
        self.assertEqual(set(SKILLS), {entry["skill"] for entry in entries})
        absolute_user_prefix = "/" + "Users" + "/"
        for entry in entries:
            self.assertEqual(
                {"skill", "path", "source_label", "before_sha256", "after_sha256", "change_kind"},
                set(entry),
            )
            self.assertTrue(entry["path"].startswith("skills/"))
            self.assertNotIn(absolute_user_prefix, json.dumps(entry))
            self.assertNotIn("/private/tmp", json.dumps(entry))
            self.assertNotIn("arena", json.dumps(entry).casefold())
            self.assertTrue(entry["before_sha256"] == "ABSENT" or HEX64.fullmatch(entry["before_sha256"]))
            self.assertTrue(HEX64.fullmatch(entry["after_sha256"]))
            self.assertIn(entry["change_kind"], {"added", "modified"})
            self.assertEqual(
                entry["after_sha256"],
                __import__("hashlib").sha256((ROOT / entry["path"]).read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
