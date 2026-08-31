"""Contract tests for the answer-neutral pilot semantic-detection record."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_pilot_detection.py"
CATALOG = ROOT / "skills/agent-system-integration-audit/fixtures/catalog.json"


def load_validator():
    if not SCRIPT.is_file():
        raise AssertionError(f"missing detection validator: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("pilot_detection_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def positive_record() -> dict[str, object]:
    return {
        "material_finding": True,
        "summary": "The comparison mixes a normalized ratio with a percent threshold.",
        "evidence": [
            {"path": "src/contracts.py", "line": 121},
            {"path": "src/integration.py", "line": 31},
        ],
    }


class PilotDetectionValidatorTests(unittest.TestCase):
    def test_accepts_positive_record_with_anchor_and_unique_support(self) -> None:
        module = load_validator()
        self.assertEqual(
            [],
            module.validate_detection(positive_record(), True, "src/contracts.py:121"),
        )

    def test_accepts_closed_clean_record(self) -> None:
        module = load_validator()
        record = {"material_finding": False, "summary": None, "evidence": []}
        self.assertEqual([], module.validate_detection(record, False, None))

    def test_rejects_false_verdict_missing_anchor_and_duplicate_identity(self) -> None:
        module = load_validator()
        false_negative = {"material_finding": False, "summary": None, "evidence": []}
        self.assertIn(
            "material_finding does not match the selected case",
            module.validate_detection(false_negative, True, "src/contracts.py:121"),
        )

        missing = positive_record()
        missing["evidence"] = [{"path": "src/integration.py", "line": 31}]
        self.assertIn(
            "expected evidence anchor must appear exactly once",
            module.validate_detection(missing, True, "src/contracts.py:121"),
        )

        repeated = positive_record()
        repeated["evidence"] = [
            {"path": "src/contracts.py", "line": 121},
            {"path": "SRC/contracts.py", "line": 121},
        ]
        self.assertIn(
            "evidence identities must be portable and unique",
            module.validate_detection(repeated, True, "src/contracts.py:121"),
        )

    def test_rejects_unsafe_or_noncanonical_record_fields(self) -> None:
        module = load_validator()
        record = positive_record()
        record["summary"] = "visible\ncontrol"
        evidence = record["evidence"]
        assert isinstance(evidence, list)
        evidence[0] = {"path": "../contracts.py", "line": True}
        errors = module.validate_detection(record, True, "src/contracts.py:121")
        self.assertIn("summary must be a non-empty single-line string", errors)
        self.assertIn("evidence path must be a canonical relative path", errors)
        self.assertIn("evidence line must be a positive integer", errors)

    def test_cli_binds_record_to_the_internal_catalog_case(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            record_path = Path(temporary) / "detection-record.json"
            record_path.write_text(json.dumps(positive_record()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--record",
                    str(record_path),
                    "--catalog",
                    str(CATALOG),
                    "--case",
                    "D12-SEMANTIC",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual({"status": "valid"}, json.loads(result.stdout))
            self.assertEqual("", result.stderr)


if __name__ == "__main__":
    unittest.main()
