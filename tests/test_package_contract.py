from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageContractTests(unittest.TestCase):
    def test_exactly_three_approved_skills_are_packaged(self) -> None:
        skill_names = {
            path.parent.name
            for path in (ROOT / "skills").glob("*/SKILL.md")
            if path.is_file()
        }
        self.assertEqual(
            {
                "agent-system-integration-audit",
                "dual-lens-investment-review",
                "ai-anime-production-director",
            },
            skill_names,
        )

    def test_required_root_documents_exist(self) -> None:
        for name in (
            "README.md",
            "README.zh-TW.md",
            "LICENSE",
            "PUBLICATION_STATUS.md",
            "evidence/README.md",
            "evidence/benchmark-summary.json",
        ):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_status_records_dated_private_remote_handoff(self) -> None:
        status = (ROOT / "PUBLICATION_STATUS.md").read_text(encoding="utf-8")
        state_lines = [line for line in status.splitlines() if line.startswith("- State:")]
        self.assertEqual(
            state_lines,
            ["- State: `LOCAL_CANDIDATE / LIMITED EVALUATION EVIDENCE`"],
        )
        self.assertIn(
            "- Public status: `PRIVATE_REMOTE — public toggle pending owner (2026-08-31)`",
            status,
        )
        self.assertIn("2026-08-30 | Candidate snapshot before Git initialization", status)
        self.assertIn("2026-08-31 | Git initialized; private GitHub remote created", status)
        self.assertNotIn("NOT " + "PUBLIC", status)
        self.assertNotIn("not a Git " + "repository", status)
        self.assertIn(
            "- Claims gate: `EXPAND_BEFORE_PUBLIC_CLAIMS`",
            status,
        )
        self.assertIn("- Approved GitHub slug: `agent-skills-lab`", status)
        self.assertIn("- Rights: `ALL RIGHTS RESERVED / PORTFOLIO EVALUATION ONLY`", status)
        self.assertNotIn("LOCAL_PUBLICATION_READY", status)

    def test_bilingual_readmes_link_to_each_other(self) -> None:
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        self.assertIn("README.zh-TW.md", en)
        self.assertIn("README.md", zh)
