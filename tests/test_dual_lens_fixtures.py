from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/dual-lens-investment-review"
FIXTURE_ROOT = SKILL_ROOT / "fixtures"
EXPECTED_CASES = {"CASE-EMBER", "CASE-DELTA", "CASE-HARBOR", "CASE-IVORY"}
EXPECTED_DISPOSITIONS = {"BLOCK", "REVISE", "READY_FOR_HUMAN_REVIEW"}
FORBIDDEN_TERMS = {"k_react", "kairosys", "hallu", "orinx"}
TOLERATED_LIVE_RESIDUE_PARTS = {"." + "git", "__py" + "cache__"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DualLensFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads((FIXTURE_ROOT / "catalog.json").read_text(encoding="utf-8"))

    def test_catalog_has_exact_four_answer_neutral_cases(self) -> None:
        self.assertEqual({"cases"}, set(self.catalog))
        cases = self.catalog["cases"]
        self.assertEqual(EXPECTED_CASES, {case["case_id"] for case in cases})
        self.assertEqual(4, len(cases))
        for case in cases:
            self.assertEqual(
                {"case_id", "project_root", "claim_ids", "source_files"},
                set(case),
            )
            serialized = json.dumps(case, sort_keys=True).casefold()
            for forbidden in ("expected", "verdict", "answer", "material_failure"):
                self.assertNotIn(forbidden, serialized)

    def test_each_case_has_required_visible_files_and_verified_manifest(self) -> None:
        for case in self.catalog["cases"]:
            root = SKILL_ROOT / case["project_root"]
            for name in ("TASK.md", "decision-context.md", "report.md", "case-manifest.json"):
                self.assertTrue((root / name).is_file(), f"{case['case_id']}:{name}")
            manifest = json.loads((root / "case-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual({"case_id", "files"}, set(manifest))
            self.assertEqual(case["case_id"], manifest["case_id"])
            expected_paths = sorted(
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.is_file() and path.name != "case-manifest.json"
            )
            self.assertEqual(expected_paths, [item["path"] for item in manifest["files"]])
            for item in manifest["files"]:
                path = root / item["path"]
                self.assertEqual({"path", "bytes", "sha256"}, set(item))
                self.assertEqual(path.stat().st_size, item["bytes"])
                self.assertEqual(digest(path), item["sha256"])

    def test_reports_and_sources_cover_declared_claim_ids(self) -> None:
        for case in self.catalog["cases"]:
            root = SKILL_ROOT / case["project_root"]
            report = (root / "report.md").read_text(encoding="utf-8")
            self.assertTrue(case["claim_ids"])
            for claim_id in case["claim_ids"]:
                self.assertIn(f"[{claim_id}]", report)
            actual_sources = sorted(
                path.relative_to(root).as_posix() for path in (root / "sources").glob("*.md")
            )
            self.assertEqual(case["source_files"], actual_sources)
            self.assertTrue(actual_sources)

    def test_fixture_text_contains_no_private_project_terms_or_symlinks(self) -> None:
        for path in SKILL_ROOT.rglob("*"):
            self.assertFalse(path.is_symlink(), path)
            relative = path.relative_to(SKILL_ROOT)
            if (
                any(part in TOLERATED_LIVE_RESIDUE_PARTS for part in relative.parts)
                or path.name == ".DS_Store"
                or path.suffix.casefold() == ".pyc"
            ):
                continue
            if path.is_file():
                text = path.read_text(encoding="utf-8").casefold()
                for term in FORBIDDEN_TERMS:
                    self.assertNotIn(term, text, path)

    def test_evals_use_official_schema_and_all_three_system_dispositions(self) -> None:
        evals = json.loads((SKILL_ROOT / "evals/evals.json").read_text(encoding="utf-8"))
        self.assertEqual("dual-lens-investment-review", evals["skill_name"])
        self.assertEqual({1, 2, 3, 4}, {item["id"] for item in evals["evals"]})
        self.assertEqual(EXPECTED_CASES, {item["case_id"] for item in evals["evals"]})
        self.assertEqual(EXPECTED_DISPOSITIONS, {item["expected_output"] for item in evals["evals"]})
        for item in evals["evals"]:
            self.assertEqual(
                {"id", "case_id", "prompt", "expected_output", "files", "expectations"},
                set(item),
            )
            self.assertEqual(4, len(item["expectations"]))


if __name__ == "__main__":
    unittest.main()
