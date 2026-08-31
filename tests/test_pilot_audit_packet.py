"""Alias-bound grading contract for opaque pilot audit packets."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_pilot_audit_packet.py"
CATALOG = ROOT / "skills/agent-system-integration-audit/fixtures/catalog.json"


def load_validator():
    if not SCRIPT.is_file():
        raise AssertionError(f"missing pilot packet validator: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("pilot_packet_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_packet() -> dict[str, object]:
    return {
        "status": "FINDINGS_REPORTED",
        "findings": [
            {
                "finding_id": "D12-F01",
                "severity": "CRITICAL",
                "dimension": 12,
                "secondary_dimensions": [],
                "claim": "A ratio observation is compared directly with a percent threshold.",
                "expected_impact": "A breached drawdown limit can be allowed.",
                "evidence": [
                    {"path": "src/contracts.py", "line": 121, "excerpt": "threshold_basis: percent"},
                    {"path": "src/integration.py", "line": 29, "excerpt": "threshold = rule threshold"},
                ],
                "verification_command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_system.py -v",
                "observed_output": "Ran 2 tests\nOK",
                "root_closed_by": "An end-to-end regression would compare both values in one basis.",
                "residual_risk": "Only the staged evaluator was inspected.",
            }
        ],
        "scope": "CASE-MERIDIAN",
        "residual_risk": "Only the staged project was assessed.",
    }


class PilotAuditPacketValidatorTests(unittest.TestCase):
    def test_accepts_internal_truth_bound_to_opaque_executor_scope(self) -> None:
        module = load_validator()
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(
            [],
            module.validate_pilot_packet(
                valid_packet(), catalog, "D12-SEMANTIC", "CASE-MERIDIAN"
            ),
        )

    def test_rejects_wrong_scope_or_rebound_internal_case(self) -> None:
        module = load_validator()
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        wrong_scope = valid_packet()
        wrong_scope["scope"] = "D12-SEMANTIC"
        self.assertIn(
            "packet scope must exactly match case_id",
            module.validate_pilot_packet(
                wrong_scope, catalog, "D12-SEMANTIC", "CASE-MERIDIAN"
            ),
        )
        self.assertIn(
            "executor case ID is not bound to the selected internal case",
            module.validate_pilot_packet(
                valid_packet(), catalog, "D08-ADAPTER", "CASE-MERIDIAN"
            ),
        )

    def test_cli_accepts_only_the_closed_four_flag_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            packet_path = Path(temporary) / "audit-packet.json"
            packet_path.write_text(json.dumps(valid_packet()), encoding="utf-8")
            valid = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--packet",
                    str(packet_path),
                    "--catalog",
                    str(CATALOG),
                    "--case",
                    "D12-SEMANTIC",
                    "--executor-case",
                    "CASE-MERIDIAN",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(valid.returncode, 0, valid.stdout)
            self.assertEqual({"status": "valid"}, json.loads(valid.stdout))
            invalid = subprocess.run(
                [sys.executable, str(SCRIPT), "--packet", str(packet_path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual({"errors"}, set(json.loads(invalid.stdout)))
            self.assertEqual("", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
