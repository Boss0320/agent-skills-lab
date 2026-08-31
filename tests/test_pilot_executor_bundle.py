from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "assemble_pilot_executor_bundle.py"
SKILL_ROOT = ROOT / "skills" / "agent-system-integration-audit"
CASE_FILES = {
    "case-manifest.json",
    "src/contracts.py",
    "src/component.py",
    "src/integration.py",
    "config/system.json",
    "tests/test_system.py",
}
SKILL_FILES = {
    "SKILL.md",
    "references/audit-contract.md",
    "references/detection-workflow.md",
    "scripts/validate_detection_record.py",
}
PILOT_CASE_ALIASES = {
    "D03-DATAFLOW": "CASE-CEDAR",
    "D02-SCHEMA": "CASE-EMBER",
    "D08-ADAPTER": "CASE-HARBOR",
    "D12-SEMANTIC": "CASE-MERIDIAN",
    "CLEAN-01": "CASE-JUNIPER",
    "CLEAN-02": "CASE-WILLOW",
    "D11-REQUIRED-PATH": "CASE-COBALT",
    "CLEAN-03": "CASE-SABLE",
}
GOLD_TOKENS = (
    "seeded_findings",
    "expected_finding_ids",
    "expected_evidence",
    "D02-F01",
    "D08-F01",
    "src/contracts.py:21",
    "src/component.py:81",
    "Find D02-F01",
    "Find D08-F01",
    "Cites catalog-bound evidence",
    "D12-SEMANTIC",
    "D12-F01",
    "src/contracts.py:121",
    "CLEAN-01",
    "CLEAN-02",
    "D03-F01",
    "D11-F01",
    "CLEAN-03",
    "clean_control",
)


def _load_bundle_module():
    if not SCRIPT_PATH.is_file():
        raise AssertionError(f"missing bundle script: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("assemble_pilot_executor_bundle", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def _text(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*") if path.is_file())


class PilotExecutorBundleTests(unittest.TestCase):
    def test_all_bundles_use_opaque_case_ids_and_answer_free_byte_identical_sources(self) -> None:
        module = _load_bundle_module()
        with tempfile.TemporaryDirectory() as temporary:
            for case_id, alias in PILOT_CASE_ALIASES.items():
                destination = Path(temporary) / alias
                result = module.assemble_pilot_bundle(ROOT, case_id, destination)
                self.assertEqual(
                    result,
                    {
                        "case_id": case_id,
                        "executor_case_id": alias,
                        "project_files": 6,
                        "skill_files": len(SKILL_FILES),
                    },
                )
                self.assertEqual(_files(destination / "project"), CASE_FILES)
                self.assertEqual(_files(destination / "skill"), SKILL_FILES)

                staged_manifest = json.loads(
                    (destination / "project" / "case-manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual(staged_manifest["case_id"], alias)

                case_root = SKILL_ROOT / "fixtures" / "cases" / case_id
                for relative in CASE_FILES - {"case-manifest.json"}:
                    self.assertEqual(
                        (destination / "project" / relative).read_bytes(),
                        (case_root / relative).read_bytes(),
                    )
                for relative in SKILL_FILES:
                    self.assertEqual(
                        (destination / "skill" / relative).read_bytes(),
                        (SKILL_ROOT / relative).read_bytes(),
                    )

                executor_text = _text(destination / "project") + _text(destination / "skill")
                for token in GOLD_TOKENS:
                    self.assertNotIn(token, executor_text, f"{case_id}:{token}")
                self.assertFalse((destination / "project" / "fixtures" / "catalog.json").exists())
                self.assertFalse((destination / "skill" / "evals").exists())
                self.assertFalse((destination / "skill" / "scripts" / "validate_audit_packet.py").exists())

    def test_answer_bearing_or_digest_rebound_manifest_is_rejected(self) -> None:
        module = _load_bundle_module()
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "candidate"
            shutil.copytree(ROOT, copied)
            manifest_path = (
                copied
                / "skills"
                / "agent-system-integration-audit"
                / "fixtures"
                / "cases"
                / "D02-SCHEMA"
                / "case-manifest.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["seeded_findings"] = [{"finding_id": "D02-F01"}]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            answer_target = Path(temporary) / PILOT_CASE_ALIASES["D02-SCHEMA"]
            with self.assertRaises(module.PilotBundleError):
                module.assemble_pilot_bundle(copied, "D02-SCHEMA", answer_target)
            self.assertFalse(answer_target.exists())

            del manifest["seeded_findings"]
            manifest["file_sha256"]["src/contracts.py"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            digest_target = Path(temporary) / PILOT_CASE_ALIASES["D02-SCHEMA"]
            with self.assertRaises(module.PilotBundleError):
                module.assemble_pilot_bundle(copied, "D02-SCHEMA", digest_target)
            self.assertFalse(digest_target.exists())

    def test_cli_accepts_one_closed_shape_and_rejects_unsafe_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid_destination = root / PILOT_CASE_ALIASES["CLEAN-01"]
            valid = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case",
                    "CLEAN-01",
                    "--destination",
                    str(valid_destination),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertEqual(valid.stderr, "")
            self.assertEqual(
                json.loads(valid.stdout),
                {
                    "case_id": "CLEAN-01",
                    "executor_case_id": PILOT_CASE_ALIASES["CLEAN-01"],
                    "project_files": 6,
                    "skill_files": len(SKILL_FILES),
                },
            )

            invalid_cases = (
                ([], None),
                (["D02-SCHEMA", str(root / "positional")], root / "positional"),
                (["--case", "D02-SCHEMA", "--case", "D08-ADAPTER"], None),
                (
                    ["--unknown", "D02-SCHEMA", "--destination", str(root / "unknown-flag")],
                    root / "unknown-flag",
                ),
                (
                    ["--case", "NOT-A-CASE", "--destination", str(root / "unknown-case")],
                    root / "unknown-case",
                ),
                (["--case", "D02-SCHEMA", "--destination", "-unsafe"], None),
            )
            for arguments, target in invalid_cases:
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT_PATH), *arguments],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(set(json.loads(result.stdout)), {"errors"})
                    if target is not None:
                        self.assertFalse(target.exists())

            existing = root / "existing"
            existing.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--case",
                    "D02-SCHEMA",
                    "--destination",
                    str(existing),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, "")
            self.assertEqual(set(json.loads(result.stdout)), {"errors"})

    def test_destination_text_is_canonical_in_parser_and_real_cli(self) -> None:
        module = _load_bundle_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = str(root)
            unsafe_values = (
                f"{raw_root}/line\nbreak",
                f"{raw_root}/tab\tbreak",
                f"{raw_root}/format\u200bmark",
                f"{raw_root}//repeated",
                f"{raw_root}/trailing/",
                f"{raw_root}/./dot-alias",
                f"{raw_root}/nested/../dotdot-alias",
                f"{raw_root}/back\\slash",
                f"{raw_root}/{unicodedata.normalize('NFD', 'é')}",
            )
            self.assertIsNone(
                module._parse_arguments(
                    ["--case", "D02-SCHEMA", "--destination", f"{raw_root}/nul\x00path"]
                )
            )
            for value in unsafe_values:
                with self.subTest(value=repr(value)):
                    arguments = ["--case", "D02-SCHEMA", "--destination", value]
                    self.assertIsNone(module._parse_arguments(arguments))
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT_PATH), *arguments],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(set(json.loads(result.stdout)), {"errors"})
                    self.assertFalse(Path(value).exists())

            existing = root / "canonical-existing"
            existing.mkdir()
            existing_arguments = [
                "--case",
                "D02-SCHEMA",
                "--destination",
                str(existing),
            ]
            self.assertEqual(
                module._parse_arguments(existing_arguments),
                ("D02-SCHEMA", existing),
            )
            existing_result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), *existing_arguments],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(existing_result.returncode, 2)
            self.assertEqual(existing_result.stderr, "")
            self.assertEqual(set(json.loads(existing_result.stdout)), {"errors"})
            self.assertEqual(list(existing.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
