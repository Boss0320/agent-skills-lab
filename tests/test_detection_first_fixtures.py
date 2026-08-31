from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "agent-system-integration-audit"
CASES_ROOT = SKILL_ROOT / "fixtures" / "cases"
CASE_INFO = {
    "D03-DATAFLOW": ("CedarSignals", "src/integration.py:8"),
    "D11-REQUIRED-PATH": ("CobaltDispatch", "src/integration.py:15"),
    "CLEAN-03": ("SableFallback", None),
}
CASE_FILES = {
    "src/contracts.py",
    "src/component.py",
    "src/integration.py",
    "config/system.json",
    "tests/test_system.py",
}
FORBIDDEN_SOURCE_TERMS = {
    "expected_finding",
    "grader",
    "answer_key",
    "material_failure",
    "clean_control",
}


def run_test(case_id: str, target: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "unittest", target, "-v"],
        cwd=CASES_ROOT / case_id,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )


class DetectionFirstFixtureTests(unittest.TestCase):
    def test_three_cases_have_exact_answer_neutral_manifest_bound_files(self) -> None:
        for case_id, (project_name, _) in CASE_INFO.items():
            root = CASES_ROOT / case_id
            self.assertTrue(root.is_dir(), case_id)
            self.assertFalse(root.is_symlink(), case_id)
            actual = {
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.is_file() and path.name != "case-manifest.json"
            }
            self.assertEqual(CASE_FILES, actual, case_id)
            manifest = json.loads((root / "case-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual({"case_id", "project_name", "file_sha256"}, set(manifest))
            self.assertEqual(case_id, manifest["case_id"])
            self.assertEqual(project_name, manifest["project_name"])
            self.assertEqual(CASE_FILES, set(manifest["file_sha256"]))
            for relative, digest in manifest["file_sha256"].items():
                self.assertEqual(
                    digest,
                    hashlib.sha256((root / relative).read_bytes()).hexdigest(),
                    f"{case_id}:{relative}",
                )
            source_text = "\n".join(
                (root / relative).read_text(encoding="utf-8") for relative in CASE_FILES
            ).casefold()
            for forbidden in FORBIDDEN_SOURCE_TERMS:
                self.assertNotIn(forbidden, source_text, f"{case_id}:{forbidden}")

    def test_isolated_components_are_green_but_have_limited_reach(self) -> None:
        for case_id in CASE_INFO:
            completed = run_test(case_id, "tests.test_system.IsolatedComponentTests")
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("OK", completed.stderr)

    def test_dataflow_required_path_exposes_dropped_decision_basis(self) -> None:
        completed = run_test("D03-DATAFLOW", "tests.test_system.RequiredPathTests")
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("decision_basis", completed.stderr)

    def test_required_path_canary_exposes_missing_audit_event(self) -> None:
        completed = run_test("D11-REQUIRED-PATH", "tests.test_system.RequiredPathTests")
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("approval audit event missing", completed.stderr)

    def test_suspicious_fallback_clean_control_passes_the_same_probe_class(self) -> None:
        completed = run_test("CLEAN-03", "tests.test_system.RequiredPathTests")
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("OK", completed.stderr)

    def test_catalog_identities_bind_the_positive_cases_without_entering_sources(self) -> None:
        catalog = json.loads((SKILL_ROOT / "fixtures" / "catalog.json").read_text(encoding="utf-8"))
        by_id = {case["case_id"]: case for case in catalog["cases"]}
        self.assertEqual(set(CASE_INFO), set(CASE_INFO) & set(by_id))
        for case_id, (_, identity) in CASE_INFO.items():
            case = by_id[case_id]
            if identity is None:
                self.assertTrue(case["clean_control"])
                self.assertEqual({}, case["expected_evidence"])
            else:
                self.assertFalse(case["clean_control"])
                self.assertEqual([identity], list(case["expected_evidence"].values()))


if __name__ == "__main__":
    unittest.main()
