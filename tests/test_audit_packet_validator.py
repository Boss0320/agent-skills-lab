"""Contract tests for the synthetic integration-audit packet validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import copy
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/agent-system-integration-audit/scripts/validate_audit_packet.py"
CATALOG = ROOT / "skills/agent-system-integration-audit/fixtures/catalog.json"


def load_validator():
    spec = importlib.util.spec_from_file_location("audit_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_case() -> dict[str, object]:
    return {
        "case_id": "D12-SEMANTIC",
        "dimension": 12,
        "severity": "CRITICAL",
        "expected_finding_ids": ["D12-F01"],
        "clean_control": False,
        "project_root": "fixtures/cases/D12-SEMANTIC",
        "expected_evidence": {"D12-F01": "src/contracts.py:121"},
    }


def valid_finding() -> dict[str, object]:
    return {
        "finding_id": "D12-F01",
        "severity": "CRITICAL",
        "dimension": 12,
        "secondary_dimensions": [],
        "claim": "The report period was read as a fiscal year instead of a quarter.",
        "expected_impact": "The analysis could compare incompatible reporting periods.",
        "evidence": [{"path": "src/contracts.py", "line": 121, "excerpt": "period = annual"}],
        "verification_command": "python3 -m unittest tests.test_report -v",
        "observed_output": "FAILED: quarter value was replaced",
        "root_closed_by": "test_report_preserves_quarterly_period asserts the stated period.",
        "residual_risk": "Other report inputs remain outside this synthetic case.",
    }


def valid_packet() -> dict[str, object]:
    return {
        "status": "FINDINGS_REPORTED",
        "findings": [valid_finding()],
        "scope": "D12-SEMANTIC",
        "residual_risk": "Only the declared case was assessed.",
    }


def catalog_cases() -> dict[str, dict[str, object]]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {case["case_id"]: case for case in catalog["cases"]}


def packet_for_case(case: dict[str, object]) -> dict[str, object]:
    if case["clean_control"]:
        return {
            "status": "CLEAN_CONTROL_PASS",
            "findings": [],
            "scope": case["case_id"],
            "residual_risk": "Only this synthetic case was assessed.",
        }
    findings = []
    for finding_id in case["expected_finding_ids"]:
        finding = valid_finding()
        path, line = case["expected_evidence"][finding_id].rsplit(":", 1)
        finding.update(
            {
                "finding_id": finding_id,
                "severity": case["severity"],
                "dimension": case["dimension"],
                "evidence": [{"path": path, "line": int(line), "excerpt": "seeded evidence"}],
            }
        )
        findings.append(finding)
    return {
        "status": "FINDINGS_REPORTED",
        "findings": findings,
        "scope": case["case_id"],
        "residual_risk": "Only this synthetic case was assessed.",
    }


def run_cli(packet_path: Path, catalog_path: Path = CATALOG, case_id: str = "D12-SEMANTIC") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--packet",
            str(packet_path),
            "--catalog",
            str(catalog_path),
            "--case",
            case_id,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class AuditPacketValidatorTests(unittest.TestCase):
    def test_accepts_a_complete_seeded_packet(self) -> None:
        module = load_validator()
        self.assertEqual([], module.validate_packet(valid_packet(), valid_case()))

    def test_rejects_legacy_or_unknown_packet_keys(self) -> None:
        module = load_validator()
        packet = {"findings": [valid_finding()]}
        self.assertIn("packet keys must be exact", module.validate_packet(packet, valid_case()))

    def test_rejects_a_malformed_case_without_raising(self) -> None:
        module = load_validator()
        case = valid_case()
        case["expected_finding_ids"] = None
        self.assertIn(
            "expected_finding_ids must be non-empty strings",
            module.validate_packet(valid_packet(), case),
        )

    def test_rejects_invalid_status_combinations(self) -> None:
        module = load_validator()
        packet = valid_packet()
        packet["status"] = "CLEAN_CONTROL_PASS"
        self.assertIn(
            "CLEAN_CONTROL_PASS requires empty findings",
            module.validate_packet(packet, valid_case()),
        )

    def test_rejects_json_scalar_shapes_without_raising(self) -> None:
        module = load_validator()
        for malformed in ([], {}, None, True, 1, 1.5):
            packet = valid_packet()
            packet["status"] = malformed
            self.assertTrue(module.validate_packet(packet, valid_case()))
            packet = valid_packet()
            finding = packet["findings"][0]
            assert isinstance(finding, dict)
            finding["severity"] = malformed
            self.assertTrue(module.validate_packet(packet, valid_case()))
            case = valid_case()
            case["severity"] = malformed
            self.assertTrue(module.validate_packet(valid_packet(), case))

        oversized_case = valid_case()
        oversized_case["expected_evidence"] = {
            "D12-F01": f"src/report.py:{'9' * 5000}"
        }
        self.assertTrue(module.validate_packet(valid_packet(), oversized_case))

    def test_rejects_duplicate_finding_ids(self) -> None:
        module = load_validator()
        packet = valid_packet()
        packet["findings"] = [valid_finding(), valid_finding()]
        self.assertIn(
            "duplicate finding id D12-F01",
            module.validate_packet(packet, valid_case()),
        )

    def test_rejects_missing_or_unexpected_material_findings(self) -> None:
        module = load_validator()
        missing = valid_packet()
        missing["findings"] = []
        self.assertIn(
            "missing expected finding D12-F01",
            module.validate_packet(missing, valid_case()),
        )
        extra = valid_packet()
        finding = valid_finding()
        finding["finding_id"] = "UNEXPECTED-F01"
        extra["findings"] = [finding]
        self.assertIn(
            "unexpected material finding UNEXPECTED-F01",
            module.validate_packet(extra, valid_case()),
        )

    def test_rejects_seeded_dimension_or_severity_mismatch(self) -> None:
        module = load_validator()
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        finding["dimension"] = 2
        finding["severity"] = "MATERIAL"
        errors = module.validate_packet(packet, valid_case())
        self.assertIn("dimension mismatch for D12-F01", errors)
        self.assertIn("severity mismatch for D12-F01", errors)

    def test_rejects_malformed_secondary_dimensions_and_bool_integers(self) -> None:
        module = load_validator()
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        finding["secondary_dimensions"] = [12, True]
        evidence = finding["evidence"][0]
        assert isinstance(evidence, dict)
        evidence["line"] = True
        errors = module.validate_packet(packet, valid_case())
        self.assertIn("secondary_dimensions must contain unique dimensions 1 through 12", errors)
        self.assertIn("evidence line must be a positive integer", errors)

    def test_rejects_evidence_that_does_not_match_the_seed_identity(self) -> None:
        module = load_validator()
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        evidence = finding["evidence"][0]
        assert isinstance(evidence, dict)
        evidence["line"] = 122
        self.assertIn(
            "evidence mismatch for D12-F01",
            module.validate_packet(packet, valid_case()),
        )

    def test_accepts_unique_supporting_evidence_with_one_catalog_anchor(self) -> None:
        module = load_validator()
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        finding["evidence"] = [
            {"path": "src/contracts.py", "line": 121, "excerpt": "period = annual"},
            {"path": "src/integration.py", "line": 13, "excerpt": "consumer expects quarter"},
        ]
        self.assertEqual([], module.validate_packet(packet, valid_case()))

    def test_accepts_lf_multiline_observed_output(self) -> None:
        module = load_validator()
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        finding["observed_output"] = (
            "test_report_preserves_quarterly_period ... FAIL\n"
            "AssertionError: quarter value was replaced"
        )
        self.assertEqual([], module.validate_packet(packet, valid_case()))

    def test_rejects_missing_or_repeated_catalog_anchor(self) -> None:
        module = load_validator()

        missing = valid_packet()
        missing_finding = missing["findings"][0]
        assert isinstance(missing_finding, dict)
        missing_finding["evidence"] = [
            {"path": "src/integration.py", "line": 13, "excerpt": "consumer expects quarter"}
        ]
        self.assertIn(
            "evidence mismatch for D12-F01",
            module.validate_packet(missing, valid_case()),
        )

        repeated = valid_packet()
        repeated_finding = repeated["findings"][0]
        assert isinstance(repeated_finding, dict)
        repeated_finding["evidence"] = [
            {"path": "src/contracts.py", "line": 121, "excerpt": "first anchor"},
            {"path": "src/contracts.py", "line": 121, "excerpt": "repeated anchor"},
        ]
        repeated_errors = module.validate_packet(repeated, valid_case())
        self.assertIn("evidence identities must be unique", repeated_errors)
        self.assertIn("evidence mismatch for D12-F01", repeated_errors)

    def test_observed_output_rejects_controls_other_than_lf(self) -> None:
        module = load_validator()
        for control in ("\r", "\t", "\x00", "\u200b"):
            packet = valid_packet()
            finding = packet["findings"][0]
            assert isinstance(finding, dict)
            finding["observed_output"] = f"first{control}second"
            self.assertIn(
                "observed_output must be a non-empty string",
                module.validate_packet(packet, valid_case()),
                repr(control),
            )

    def test_rejects_empty_closure_fields_and_unsafe_evidence_paths(self) -> None:
        module = load_validator()
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        for field in (
            "verification_command",
            "observed_output",
            "root_closed_by",
            "residual_risk",
        ):
            finding[field] = ""
        evidence = finding["evidence"][0]
        assert isinstance(evidence, dict)
        evidence["path"] = "../secret.py"
        errors = module.validate_packet(packet, valid_case())
        self.assertIn("verification_command must be a non-empty string", errors)
        self.assertIn("observed_output must be a non-empty string", errors)
        self.assertIn("root_closed_by must be a non-empty string", errors)
        self.assertIn("residual_risk must be a non-empty string", errors)
        self.assertIn("evidence path must be a safe relative path", errors)

    def test_rejects_material_false_positive_on_clean_control_but_allows_minor(self) -> None:
        module = load_validator()
        clean_case = valid_case()
        clean_case.update(
            {
                "case_id": "CLEAN-01",
                "dimension": None,
                "severity": None,
                "expected_finding_ids": [],
                "clean_control": True,
                "project_root": "fixtures/cases/clean-01",
                "expected_evidence": {},
            }
        )
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        finding["finding_id"] = "FP-1"
        finding["severity"] = "MATERIAL"
        self.assertIn("material false positive FP-1", module.validate_packet(packet, clean_case))
        finding["severity"] = "MINOR"
        packet["scope"] = "CLEAN-01"
        self.assertEqual([], module.validate_packet(packet, clean_case))

    def test_rejects_packets_bound_to_a_different_case(self) -> None:
        module = load_validator()
        cases = catalog_cases()
        for packet_case_id, packet_case in cases.items():
            packet = packet_for_case(packet_case)
            for selected_case_id, selected_case in cases.items():
                errors = module.validate_packet(packet, selected_case)
                if packet_case_id == selected_case_id:
                    self.assertEqual([], errors, f"{packet_case_id} must validate itself")
                else:
                    self.assertIn(
                        "packet scope must exactly match case_id",
                        errors,
                        f"{packet_case_id} must not validate as {selected_case_id}",
                    )

        clean_minor = packet_for_case(cases["CLEAN-01"])
        clean_minor["status"] = "FINDINGS_REPORTED"
        clean_minor["findings"] = [
            {
                **valid_finding(),
                "finding_id": "CLEAN-MINOR-F01",
                "severity": "MINOR",
                "dimension": 7,
                "evidence": [{"path": "src/imports.py", "line": 6, "excerpt": "minor"}],
            }
        ]
        self.assertEqual([], module.validate_packet(clean_minor, cases["CLEAN-01"]))
        self.assertIn(
            "packet scope must exactly match case_id",
            module.validate_packet(clean_minor, cases["CLEAN-02"]),
        )

    def test_rejects_control_text_noncanonical_paths_and_duplicate_evidence(self) -> None:
        module = load_validator()
        for value in ("\x00", "\x7f", "\u200b", "\u2060"):
            packet = valid_packet()
            packet["scope"] = value
            self.assertTrue(module.validate_packet(packet, valid_case()))
            packet = valid_packet()
            finding = packet["findings"][0]
            assert isinstance(finding, dict)
            finding["claim"] = value
            self.assertTrue(module.validate_packet(packet, valid_case()))
        for path in ("C:/outside.py", "src\\report.py", "./src/report.py", "src//report.py", ".hidden/report.py", "src/../report.py"):
            packet = valid_packet()
            finding = packet["findings"][0]
            assert isinstance(finding, dict)
            finding["evidence"] = [{"path": path, "line": 14, "excerpt": "bad path"}]
            self.assertIn("evidence path must be a safe relative path", module.validate_packet(packet, valid_case()))
        packet = valid_packet()
        finding = packet["findings"][0]
        assert isinstance(finding, dict)
        finding["evidence"] = [
            {"path": "src/report.py", "line": 14, "excerpt": "first"},
            {"path": "src/report.py", "line": 14, "excerpt": "second"},
        ]
        errors = module.validate_packet(packet, valid_case())
        self.assertIn("evidence identities must be unique", errors)
        self.assertIn("evidence mismatch for D12-F01", errors)

    def test_rejects_rebound_frozen_catalog_fields_in_api_and_cli(self) -> None:
        module = load_validator()
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        mutations: list[tuple[str, dict[str, object], str]] = []

        two_seeds = copy.deepcopy(catalog)
        case = two_seeds["cases"][0]
        case["expected_finding_ids"].append("D01-F02")
        case["expected_evidence"]["D01-F02"] = "src/contracts.py:12"
        mutations.append(("d-case-two-seeds", two_seeds, "D01-DEPENDENCY"))

        mixed_one_seed = copy.deepcopy(catalog)
        case = mixed_one_seed["cases"][14]
        case["expected_finding_ids"] = ["MIXED-C-F01"]
        case["expected_evidence"] = {"MIXED-C-F01": "src/component.py:141"}
        mutations.append(("mixed-one-seed", mixed_one_seed, "MIXED-CRITICAL-01"))

        reclassified = copy.deepcopy(catalog)
        reclassified["cases"][14]["dimension"] = 1
        reclassified["cases"][14]["severity"] = "MINOR"
        mutations.append(("mixed-reclassified", reclassified, "MIXED-CRITICAL-01"))

        rebound = copy.deepcopy(catalog)
        case = rebound["cases"][11]
        case["expected_finding_ids"] = ["RENAMED"]
        case["expected_evidence"] = {"RENAMED": "src/contracts.py:121"}
        mutations.append(("seed-rebound", rebound, "D12-SEMANTIC"))

        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            catalog_path = temp / "catalog.json"
            packet_path = temp / "packet.json"
            for name, mutation, case_id in mutations:
                self.assertTrue(module.validate_catalog(mutation)[0], name)
                case = next(item for item in mutation["cases"] if item["case_id"] == case_id)
                packet_path.write_text(json.dumps(packet_for_case(case)), encoding="utf-8")
                catalog_path.write_text(json.dumps(mutation), encoding="utf-8")
                result = run_cli(packet_path, catalog_path, case_id)
                self.assertEqual(2, result.returncode, name)
                self.assertIn("errors", json.loads(result.stdout), name)
                self.assertEqual("", result.stderr, name)

    def test_rejects_nonportable_catalog_and_packet_path_aliases_in_api_and_cli(self) -> None:
        module = load_validator()
        for path in (
            "src/café.py",
            "src/cafe\u0301.py",
            "src/trailing.",
            "src/trailing ",
            "src/\ud800.py",
        ):
            self.assertFalse(module._canonical_relative_path(path), path)

        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        mutations: list[tuple[str, dict[str, object], str]] = []
        for name, root, identity in (
            ("casefold-root", "fixtures/cases/d01-dependency", "src/contracts.py:11"),
            ("nfc-evidence", "fixtures/cases/D01-DEPENDENCY", "src/café.py:11"),
            ("nfd-evidence", "fixtures/cases/D01-DEPENDENCY", "src/cafe\u0301.py:11"),
            ("suffix-evidence", "fixtures/cases/D01-DEPENDENCY", "src/contracts.py.:11"),
            ("surrogate-evidence", "fixtures/cases/D01-DEPENDENCY", "src/\ud800.py:11"),
        ):
            mutation = copy.deepcopy(catalog)
            mutation["cases"][0]["project_root"] = root
            mutation["cases"][0]["expected_evidence"] = {"D01-F01": identity}
            mutations.append((name, mutation, "D01-DEPENDENCY"))

        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            catalog_path = temp / "catalog.json"
            packet_path = temp / "packet.json"
            for name, mutation, case_id in mutations:
                self.assertTrue(module.validate_catalog(mutation)[0], name)
                case = next(item for item in mutation["cases"] if item["case_id"] == case_id)
                packet_path.write_text(json.dumps(packet_for_case(case)), encoding="utf-8")
                catalog_path.write_text(json.dumps(mutation), encoding="utf-8")
                result = run_cli(packet_path, catalog_path, case_id)
                self.assertEqual(2, result.returncode, name)
                self.assertIn("errors", json.loads(result.stdout), name)
                self.assertEqual("", result.stderr, name)

    def test_rejects_cross_platform_evidence_aliases_and_windows_segments(self) -> None:
        module = load_validator()
        invalid_paths = (
            "src/CON",
            "src/AUX.py",
            "src/COM1",
            "src/LPT9.txt",
            "src/foo?.py",
            "src/foo|bar.py",
            "src/foo<bar.py",
            "src/foo>bar.py",
            'src/foo"bar.py',
        )
        self.assertTrue(module._canonical_relative_path("src/a-b_c.1.py"))
        for path in invalid_paths:
            self.assertFalse(module._canonical_relative_path(path), path)

        clean_case = catalog_cases()["CLEAN-01"]
        alias_packet = {
            "status": "FINDINGS_REPORTED",
            "findings": [
                {
                    **valid_finding(),
                    "finding_id": "CLEAN-MINOR-ALIAS",
                    "severity": "MINOR",
                    "dimension": 7,
                    "evidence": [
                        {"path": "src/A.py", "line": 1, "excerpt": "first"},
                        {"path": "src/a.py", "line": 1, "excerpt": "case alias"},
                    ],
                }
            ],
            "scope": "CLEAN-01",
            "residual_risk": "Only this synthetic clean case was assessed.",
        }
        self.assertIn("evidence identities must be unique", module.validate_packet(alias_packet, clean_case))

        with tempfile.TemporaryDirectory() as directory:
            packet_path = Path(directory) / "packet.json"
            packet_path.write_text(json.dumps(alias_packet), encoding="utf-8")
            result = run_cli(packet_path, case_id="CLEAN-01")
            self.assertEqual(2, result.returncode)
            self.assertIn("errors", json.loads(result.stdout))
            self.assertEqual("", result.stderr)

            for path in invalid_paths:
                packet = copy.deepcopy(alias_packet)
                finding = packet["findings"][0]
                assert isinstance(finding, dict)
                finding["evidence"] = [{"path": path, "line": 1, "excerpt": "bad"}]
                self.assertIn("evidence path must be a safe relative path", module.validate_packet(packet, clean_case), path)
                packet_path.write_text(json.dumps(packet), encoding="utf-8")
                result = run_cli(packet_path, case_id="CLEAN-01")
                self.assertEqual(2, result.returncode, path)
                self.assertIn("errors", json.loads(result.stdout), path)
                self.assertEqual("", result.stderr, path)

    def test_cli_returns_structured_json_for_valid_and_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            packet_path = temp / "packet.json"
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
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, valid.returncode)
            self.assertEqual({"status": "valid"}, json.loads(valid.stdout))
        usage = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(2, usage.returncode)
        self.assertIn("errors", json.loads(usage.stdout))

    def test_cli_rejects_utf8_catalog_and_case_errors_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            packet_path = temp / "packet.json"
            packet_path.write_bytes(b"\xff")
            invalid_utf8 = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--packet",
                    str(packet_path),
                    "--catalog",
                    str(CATALOG),
                    "--case",
                    "D12-SEMANTIC",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, invalid_utf8.returncode)
            self.assertIn("errors", json.loads(invalid_utf8.stdout))

            packet_path.write_text(json.dumps(valid_packet()), encoding="utf-8")
            catalog_path = temp / "catalog.json"
            catalog_path.write_text("{", encoding="utf-8")
            invalid_catalog = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--packet",
                    str(packet_path),
                    "--catalog",
                    str(catalog_path),
                    "--case",
                    "D12-SEMANTIC",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, invalid_catalog.returncode)
            self.assertIn("errors", json.loads(invalid_catalog.stdout))

            unknown_case = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--packet",
                    str(packet_path),
                    "--catalog",
                    str(CATALOG),
                    "--case",
                    "UNKNOWN",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, unknown_case.returncode)
            self.assertIn("errors", json.loads(unknown_case.stdout))

    def test_cli_rejects_malformed_scalars_and_duplicate_raw_json_keys(self) -> None:
        raw_packets = [
            b'{"status":[],"findings":[],"scope":"CLEAN-01","residual_risk":"risk"}',
            b'{"status":"FINDINGS_REPORTED","findings":[{"finding_id":"D12-F01","severity":[],"dimension":12,"secondary_dimensions":[],"claim":"claim","expected_impact":"impact","evidence":[{"path":"src/report.py","line":14,"excerpt":"excerpt"}],"verification_command":"cmd","observed_output":"out","root_closed_by":"test","residual_risk":"risk"}],"scope":"D12-SEMANTIC","residual_risk":"risk"}',
            b'{"status":"FINDINGS_REPORTED","status":"CLEAN_CONTROL_PASS","findings":[],"scope":"CLEAN-01","residual_risk":"risk"}',
            b'{"status":"FINDINGS_REPORTED","findings":[{"finding_id":"D12-F01","severity":"CRITICAL","severity":"CRITICAL","dimension":12,"secondary_dimensions":[],"claim":"claim","expected_impact":"impact","evidence":[{"path":"src/report.py","line":14,"excerpt":"excerpt"}],"verification_command":"cmd","observed_output":"out","root_closed_by":"test","residual_risk":"risk"}],"scope":"D12-SEMANTIC","residual_risk":"risk"}',
            b'{"status":"FINDINGS_REPORTED","findings":[{"finding_id":"D12-F01","severity":"CRITICAL","dimension":12,"secondary_dimensions":[],"claim":"claim","expected_impact":"impact","evidence":[{"path":"src/report.py","path":"src/report.py","line":14,"excerpt":"excerpt"}],"verification_command":"cmd","observed_output":"out","root_closed_by":"test","residual_risk":"risk"}],"scope":"D12-SEMANTIC","residual_risk":"risk"}',
        ]
        with tempfile.TemporaryDirectory() as directory:
            packet_path = Path(directory) / "packet.json"
            for raw_packet in raw_packets:
                packet_path.write_bytes(raw_packet)
                result = run_cli(packet_path, case_id="CLEAN-01" if b'"status":[]' in raw_packet or b'"status":"FINDINGS_REPORTED","status"' in raw_packet else "D12-SEMANTIC")
                self.assertEqual(2, result.returncode)
                self.assertIn("errors", json.loads(result.stdout))
                self.assertEqual("", result.stderr)

            packet_path.write_text(json.dumps(valid_packet()), encoding="utf-8")
            catalog_path = Path(directory) / "catalog.json"
            catalog_path.write_bytes(b'{"cases":[],"cases":[]}')
            result = run_cli(packet_path, catalog_path)
            self.assertEqual(2, result.returncode)
            self.assertIn("errors", json.loads(result.stdout))
            self.assertEqual("", result.stderr)

            catalog_path.write_bytes(b'{"cases":[{"case_id":"D12-SEMANTIC","case_id":"D12-SEMANTIC"}]}')
            result = run_cli(packet_path, catalog_path)
            self.assertEqual(2, result.returncode)
            self.assertIn("errors", json.loads(result.stdout))
            self.assertEqual("", result.stderr)

            malformed_catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
            malformed_catalog["cases"][11]["severity"] = {}
            catalog_path.write_text(json.dumps(malformed_catalog), encoding="utf-8")
            result = run_cli(packet_path, catalog_path)
            self.assertEqual(2, result.returncode)
            self.assertIn("errors", json.loads(result.stdout))
            self.assertEqual("", result.stderr)

            malformed_catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
            malformed_catalog["cases"][11]["expected_evidence"] = {
                "D12-F01": f"src/report.py:{'9' * 5000}"
            }
            catalog_path.write_text(json.dumps(malformed_catalog), encoding="utf-8")
            result = run_cli(packet_path, catalog_path)
            self.assertEqual(2, result.returncode)
            self.assertIn("errors", json.loads(result.stdout))
            self.assertEqual("", result.stderr)


if __name__ == "__main__":
    unittest.main()
