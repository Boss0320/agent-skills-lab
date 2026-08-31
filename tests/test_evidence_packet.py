from __future__ import annotations

import copy
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.verify_evidence_packet import main, sha256_file, validate_evidence_packet


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_evidence_packet.py"


def valid_packet() -> dict:
    return {
        "metadata": {
            "skill_name": "agent-system-integration-audit",
            "skill_sha256": "a" * 64,
            "executor_model": "recorded-model",
            "surface": "recorded-surface",
            "timestamp": "2026-08-28T20:40:00-07:00",
            "evals_run": [1],
            "runs_per_configuration": 1,
            "fixture_sha256": {"case-1": "b" * 64},
        },
        "runs": [
            {
                "eval_id": 1,
                "eval_name": "case-1",
                "configuration": "with_skill",
                "run_number": 1,
                "result": {
                    "pass_rate": 1.0,
                    "passed": 1,
                    "failed": 0,
                    "total": 1,
                    "time_seconds": 1.0,
                    "tokens": 10,
                    "errors": 0,
                },
                "expectations": [],
            },
            {
                "eval_id": 1,
                "eval_name": "case-1",
                "configuration": "without_skill",
                "run_number": 1,
                "result": {
                    "pass_rate": 0.0,
                    "passed": 0,
                    "failed": 1,
                    "total": 1,
                    "time_seconds": 1.0,
                    "tokens": 10,
                    "errors": 0,
                },
                "expectations": [],
            },
        ],
        "run_summary": {"with_skill": {}, "without_skill": {}, "delta": {}},
        "limitations": ["Synthetic fixtures only"],
        "claims": [],
    }


class EvidencePacketTests(unittest.TestCase):
    def assert_error(self, packet: dict, fragment: str) -> None:
        self.assertIn(fragment, "\n".join(validate_evidence_packet(packet)))

    def test_accepts_typed_packet(self) -> None:
        self.assertEqual(validate_evidence_packet(valid_packet()), [])

    def test_rejects_wrong_configuration_name(self) -> None:
        packet = valid_packet()
        packet["runs"][0]["configuration"] = "skill"
        self.assert_error(packet, "runs[0].configuration")

    def test_rejects_missing_limitations(self) -> None:
        packet = valid_packet()
        packet["limitations"] = []
        self.assert_error(packet, "limitations")

    def test_rejects_non_hex_skill_and_fixture_digests(self) -> None:
        packet = valid_packet()
        packet["metadata"]["skill_sha256"] = "g" * 64
        packet["metadata"]["fixture_sha256"]["case-1"] = "short"
        errors = "\n".join(validate_evidence_packet(packet))
        self.assertIn("metadata.skill_sha256", errors)
        self.assertIn("metadata.fixture_sha256.case-1", errors)

    def test_rejects_unpaired_duplicate_and_missing_runs(self) -> None:
        packet = valid_packet()
        packet["runs"].append(copy.deepcopy(packet["runs"][0]))
        packet["runs"] = [
            run for run in packet["runs"] if run["configuration"] != "without_skill"
        ]
        self.assert_error(packet, "duplicate")
        self.assert_error(packet, "missing paired run")

    def test_requires_every_repeat_number_for_both_configurations(self) -> None:
        packet = valid_packet()
        packet["metadata"]["runs_per_configuration"] = 3
        for run_number in (2, 3):
            for run in valid_packet()["runs"]:
                repeated = copy.deepcopy(run)
                repeated["run_number"] = run_number
                packet["runs"].append(repeated)
        packet["runs"] = [
            run
            for run in packet["runs"]
            if not (run["configuration"] == "without_skill" and run["run_number"] == 3)
        ]
        self.assert_error(packet, "missing paired run")

    def test_rejects_out_of_range_run_number_and_unlisted_eval(self) -> None:
        packet = valid_packet()
        packet["runs"][0]["run_number"] = 2
        packet["runs"][1]["eval_id"] = 2
        self.assert_error(packet, "runs[0].run_number")
        self.assert_error(packet, "runs[1].eval_id")

    def test_rejects_invalid_result_arithmetic_and_numeric_ranges(self) -> None:
        packet = valid_packet()
        result = packet["runs"][0]["result"]
        result.update(
            {
                "pass_rate": 1.2,
                "passed": 3,
                "failed": -1,
                "total": 1,
                "time_seconds": -0.1,
                "tokens": -1,
                "errors": 2,
            }
        )
        errors = "\n".join(validate_evidence_packet(packet))
        for fragment in (
            "pass_rate",
            "failed",
            "time_seconds",
            "tokens",
            "errors",
            "passed + failed must equal total",
        ):
            self.assertIn(fragment, errors)

    def test_requires_summary_sections_and_structured_claims(self) -> None:
        packet = valid_packet()
        del packet["run_summary"]["delta"]
        packet["claims"] = [{"claim": "improved"}]
        errors = "\n".join(validate_evidence_packet(packet))
        self.assertIn("run_summary.delta", errors)
        self.assertIn("claims[0].metric", errors)
        self.assertIn("claims[0].operator", errors)
        self.assertIn("claims[0].threshold", errors)

    def test_claim_metric_must_resolve_to_a_summary_number(self) -> None:
        packet = valid_packet()
        packet["run_summary"]["delta"] = {"pass_rate": 1.0}
        packet["claims"] = [
            {
                "claim": "delta.missing >= 0",
                "metric": "delta.missing",
                "operator": ">=",
                "threshold": 0,
            }
        ]
        self.assert_error(packet, "claims[0].metric")

    def test_rejects_unknown_keys_at_each_closed_object_boundary(self) -> None:
        packet = valid_packet()
        packet["unexpected"] = True
        packet["metadata"]["unexpected"] = True
        packet["runs"][0]["unexpected"] = True
        packet["runs"][0]["result"]["unexpected"] = True
        packet["run_summary"]["unexpected"] = {}
        packet["run_summary"]["with_skill"] = {"not safe!": 1, "nested": {"x": 1}}
        packet["claims"] = [
            {
                "claim": "delta.pass_rate >= 1.0",
                "metric": "delta.pass_rate",
                "operator": ">=",
                "threshold": 1.0,
                "unexpected": True,
            }
        ]
        packet["run_summary"]["delta"] = {"pass_rate": 1.0}
        errors = "\n".join(validate_evidence_packet(packet))
        for fragment in (
            "packet.unexpected",
            "metadata.unexpected",
            "runs[0].unexpected",
            "runs[0].result.unexpected",
            "run_summary.unexpected",
            "run_summary.with_skill.not safe!",
            "run_summary.with_skill.nested",
            "claims[0].unexpected",
        ):
            self.assertIn(fragment, errors)

    def test_claims_must_be_true_normalized_metric_comparisons(self) -> None:
        packet = valid_packet()
        packet["run_summary"]["delta"] = {"pass_rate": 1.0}
        packet["claims"] = [
            {
                "claim": "pass rate improved",
                "metric": "with_skill.tokens",
                "operator": ">=",
                "threshold": 10,
                "condition": "always",
            },
            {
                "claim": "delta.pass_rate > 2",
                "metric": "delta.pass_rate",
                "operator": ">",
                "threshold": 2,
            },
        ]
        errors = "\n".join(validate_evidence_packet(packet))
        self.assertIn("claims[0].claim", errors)
        self.assertIn("claims[0].metric", errors)
        self.assertIn("claims[0].condition", errors)
        self.assertIn("claims[1] condition is false", errors)

    def test_scalar_summary_section_returns_api_and_cli_validation_errors(self) -> None:
        packet = valid_packet()
        packet["run_summary"]["with_skill"] = 1
        packet["claims"] = [
            {
                "claim": "with_skill.pass_rate >= 0",
                "metric": "with_skill.pass_rate",
                "operator": ">=",
                "threshold": 0,
            }
        ]
        errors = validate_evidence_packet(packet)
        self.assertIn("run_summary.with_skill must be an object", errors)
        self.assertIn(
            "claims[0].metric must reference a numeric run_summary value", errors
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scalar-summary.json"
            path.write_text(json.dumps(packet), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn(
                "run_summary.with_skill must be an object",
                json.loads(completed.stdout)["errors"],
            )

    def test_oversized_json_integer_returns_api_and_cli_errors(self) -> None:
        packet = valid_packet()
        packet["runs"][0]["result"]["pass_rate"] = 10**400
        self.assert_error(packet, "runs[0].result.pass_rate")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.json"
            path.write_text(json.dumps(packet), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertTrue(
                any(
                    "runs[0].result.pass_rate" in error
                    for error in json.loads(completed.stdout)["errors"]
                )
            )

    def test_cli_rejects_invalid_utf8_as_json_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-utf8.json"
            path.write_bytes(b"\xff")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path)]), 2)
            self.assertEqual(
                json.loads(output.getvalue()),
                {"errors": ["input is not valid UTF-8"]},
            )
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(
                json.loads(completed.stdout),
                {"errors": ["input is not valid UTF-8"]},
            )

    def test_cli_help_is_a_json_usage_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "errors": [
                    "usage: verify_evidence_packet.py PACKET [--expected-skill-id SKILL_ID]"
                ]
            },
        )

    def test_expected_skill_id_and_sha256_file(self) -> None:
        self.assertEqual(
            validate_evidence_packet(valid_packet(), "other-skill"),
            ["metadata.skill_name does not match expected skill"],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.txt"
            path.write_bytes(b"abc")
            self.assertEqual(
                sha256_file(path),
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )

    def test_cli_returns_stable_json_for_valid_and_invalid_packets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            path.write_text(json.dumps(valid_packet()), encoding="utf-8")
            valid = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(path),
                    "--expected-skill-id",
                    "agent-system-integration-audit",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(valid.returncode, 0)
            self.assertEqual(json.loads(valid.stdout), {"errors": []})

            path.write_text("{", encoding="utf-8")
            invalid = subprocess.run(
                [sys.executable, str(SCRIPT), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(json.loads(invalid.stdout), {"errors": ["input is not valid JSON"]})


if __name__ == "__main__":
    unittest.main()
