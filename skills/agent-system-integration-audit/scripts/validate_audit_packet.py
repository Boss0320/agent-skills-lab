"""Validate closed synthetic integration-audit packets against frozen cases."""

from __future__ import annotations

import json
import sys
import unicodedata
from typing import Any


PACKET_KEYS = {"status", "findings", "scope", "residual_risk"}
FINDING_KEYS = {"finding_id", "severity", "dimension", "secondary_dimensions", "claim", "expected_impact", "evidence", "verification_command", "observed_output", "root_closed_by", "residual_risk"}
EVIDENCE_KEYS = {"path", "line", "excerpt"}
CASE_KEYS = {"case_id", "dimension", "severity", "expected_finding_ids", "clean_control", "project_root", "expected_evidence"}
SEVERITIES = {"CRITICAL", "MATERIAL", "MINOR"}
STATUSES = {"FINDINGS_REPORTED", "CLEAN_CONTROL_PASS"}
MAX_LINE = 999_999_999
FROZEN_CASE_IDS = {"D01-DEPENDENCY", "D02-SCHEMA", "D03-DATAFLOW", "D04-AUTHORITY", "D05-CONFIG", "D06-FALLBACK", "D07-IMPORT", "D08-ADAPTER", "D09-EVENT", "D10-PROMPT-TOOL", "D11-REQUIRED-PATH", "D12-SEMANTIC", "CLEAN-01", "CLEAN-02", "CLEAN-03", "MIXED-CRITICAL-01", "MIXED-MATERIAL-01"}
D_CASE_DIMENSIONS = {"D01-DEPENDENCY": 1, "D02-SCHEMA": 2, "D03-DATAFLOW": 3, "D04-AUTHORITY": 4, "D05-CONFIG": 5, "D06-FALLBACK": 6, "D07-IMPORT": 7, "D08-ADAPTER": 8, "D09-EVENT": 9, "D10-PROMPT-TOOL": 10, "D11-REQUIRED-PATH": 11, "D12-SEMANTIC": 12}
CLEAN_CASE_IDS = {"CLEAN-01", "CLEAN-02", "CLEAN-03"}
MIXED_CASE_IDS = {"MIXED-CRITICAL-01", "MIXED-MATERIAL-01"}
FROZEN_CASE_SPECS = {
    "D01-DEPENDENCY": ("fixtures/cases/D01-DEPENDENCY", 1, "MATERIAL", ("D01-F01",), ("src/contracts.py:11",)),
    "D02-SCHEMA": ("fixtures/cases/D02-SCHEMA", 2, "MATERIAL", ("D02-F01",), ("src/contracts.py:21",)),
    "D03-DATAFLOW": ("fixtures/cases/D03-DATAFLOW", 3, "MATERIAL", ("D03-F01",), ("src/integration.py:8",)),
    "D04-AUTHORITY": ("fixtures/cases/D04-AUTHORITY", 4, "CRITICAL", ("D04-F01",), ("src/component.py:41",)),
    "D05-CONFIG": ("fixtures/cases/D05-CONFIG", 5, "MATERIAL", ("D05-F01",), ("src/contracts.py:51",)),
    "D06-FALLBACK": ("fixtures/cases/D06-FALLBACK", 6, "MATERIAL", ("D06-F01",), ("src/component.py:61",)),
    "D07-IMPORT": ("fixtures/cases/D07-IMPORT", 7, "MINOR", ("D07-F01",), ("src/contracts.py:71",)),
    "D08-ADAPTER": ("fixtures/cases/D08-ADAPTER", 8, "MATERIAL", ("D08-F01",), ("src/component.py:81",)),
    "D09-EVENT": ("fixtures/cases/D09-EVENT", 9, "MATERIAL", ("D09-F01",), ("src/integration.py:91",)),
    "D10-PROMPT-TOOL": ("fixtures/cases/D10-PROMPT-TOOL", 10, "CRITICAL", ("D10-F01",), ("src/integration.py:101",)),
    "D11-REQUIRED-PATH": ("fixtures/cases/D11-REQUIRED-PATH", 11, "MATERIAL", ("D11-F01",), ("src/integration.py:15",)),
    "D12-SEMANTIC": ("fixtures/cases/D12-SEMANTIC", 12, "CRITICAL", ("D12-F01",), ("src/contracts.py:121",)),
    "CLEAN-01": ("fixtures/cases/CLEAN-01", None, None, (), ()),
    "CLEAN-02": ("fixtures/cases/CLEAN-02", None, None, (), ()),
    "CLEAN-03": ("fixtures/cases/CLEAN-03", None, None, (), ()),
    "MIXED-CRITICAL-01": ("fixtures/cases/MIXED-CRITICAL-01", 4, "CRITICAL", ("MIXED-C-F01", "MIXED-C-F02"), ("src/component.py:141", "src/integration.py:142")),
    "MIXED-MATERIAL-01": ("fixtures/cases/MIXED-MATERIAL-01", 8, "MATERIAL", ("MIXED-M-F01", "MIXED-M-F02"), ("src/contracts.py:151", "src/component.py:152")),
}


class DuplicateJsonKeyError(ValueError):
    """Raw JSON duplicate-key provenance must never be normalized away."""


def _has_forbidden_control(value: str) -> bool:
    return any(unicodedata.category(character) in {"Cc", "Cf"} for character in value)


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not _has_forbidden_control(value)


def _non_empty_observed_output(value: object) -> bool:
    """Accept exact multiline output while rejecting every control except LF."""
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not any(
            character != "\n" and unicodedata.category(character) in {"Cc", "Cf"}
            for character in value
        )
    )


def _is_dimension(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 12


def _is_line(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= MAX_LINE


def _canonical_relative_path(value: object) -> bool:
    if not _non_empty_string(value) or not isinstance(value, str):
        return False
    if not value.isascii():
        return False
    if "\\" in value or ":" in value or "//" in value or value.startswith("/"):
        return False
    return all(_safe_portable_segment(segment) for segment in value.split("/"))


def _safe_portable_segment(segment: str) -> bool:
    """Cross-platform safe names: alnum boundaries and internal ._- only."""
    if not segment or not segment[0].isalnum() or not segment[-1].isalnum():
        return False
    if any(not (character.isalnum() or character in "._-") for character in segment):
        return False
    basename = segment.split(".", 1)[0].casefold()
    return basename not in {"con", "prn", "aux", "nul"} and not (
        len(basename) == 4
        and basename[:3] in {"com", "lpt"}
        and basename[3] in "123456789"
    )


def _portability_key(value: str) -> str:
    """Canonical path policy is ASCII-only, so casefold is portable and total."""
    return value.casefold()


def _canonical_identity(value: object) -> bool:
    if not _non_empty_string(value) or not isinstance(value, str) or value.count(":") != 1:
        return False
    path, line = value.split(":")
    return _canonical_relative_path(path) and line.isascii() and line.isdecimal() and line[0] != "0" and len(line) <= 9 and (len(line) < 9 or line <= str(MAX_LINE))


def _case_errors(case: object) -> list[str]:
    if not isinstance(case, dict) or set(case) != CASE_KEYS:
        return ["case keys must be exact"]
    errors: list[str] = []
    clean = case["clean_control"]
    if not isinstance(clean, bool):
        errors.append("clean_control must be a boolean")
    if not _non_empty_string(case["case_id"]):
        errors.append("case_id must be a non-empty string")
    root = case["project_root"]
    if not (_canonical_relative_path(root) and isinstance(root, str) and root.startswith("fixtures/cases/")):
        errors.append("project_root must be a canonical fixtures/cases relative path")
    dimension, severity = case["dimension"], case["severity"]
    expected_ids, expected_evidence = case["expected_finding_ids"], case["expected_evidence"]
    if clean is True:
        if dimension is not None or severity is not None:
            errors.append("clean controls require null dimension and severity")
        if expected_ids != [] or expected_evidence != {}:
            errors.append("clean controls require no expected findings")
    else:
        if not _is_dimension(dimension):
            errors.append("case dimension must be an integer from 1 through 12")
        if not isinstance(severity, str) or severity not in SEVERITIES:
            errors.append("case severity must be CRITICAL, MATERIAL, or MINOR")
    if not isinstance(expected_ids, list) or any(not _non_empty_string(item) for item in expected_ids):
        errors.append("expected_finding_ids must be non-empty strings")
        expected_id_set: set[str] = set()
    else:
        expected_id_set = set(expected_ids)
        if len(expected_ids) != len(expected_id_set):
            errors.append("expected_finding_ids must be unique")
    if clean is False and isinstance(expected_ids, list) and not expected_ids:
        errors.append("non-clean cases require expected findings")
    if not isinstance(expected_evidence, dict):
        errors.append("expected_evidence must be an object")
    else:
        if not all(_non_empty_string(key) for key in expected_evidence):
            errors.append("expected_evidence keys must be non-empty strings")
        if set(expected_evidence) != expected_id_set:
            errors.append("expected_evidence keys must exactly match expected_finding_ids")
        if any(not _canonical_identity(identity) for identity in expected_evidence.values()):
            errors.append("expected_evidence must contain canonical path:line identities")
    return errors


def _finding_errors(finding: object) -> list[str]:
    if not isinstance(finding, dict) or set(finding) != FINDING_KEYS:
        return ["finding keys must be exact"]
    errors: list[str] = []
    if not _non_empty_string(finding["finding_id"]):
        errors.append("finding_id must be a non-empty string")
    severity = finding["severity"]
    if not isinstance(severity, str) or severity not in SEVERITIES:
        errors.append("severity must be CRITICAL, MATERIAL, or MINOR")
    if not _is_dimension(finding["dimension"]):
        errors.append("dimension must be an integer from 1 through 12")
    secondary = finding["secondary_dimensions"]
    if not isinstance(secondary, list) or any(not _is_dimension(item) for item in secondary):
        errors.append("secondary_dimensions must contain unique dimensions 1 through 12")
    elif len(secondary) != len(set(secondary)) or finding["dimension"] in secondary:
        errors.append("secondary_dimensions must contain unique dimensions 1 through 12")
    for field in ("claim", "expected_impact", "verification_command", "root_closed_by", "residual_risk"):
        if not _non_empty_string(finding[field]):
            errors.append(f"{field} must be a non-empty string")
    if not _non_empty_observed_output(finding["observed_output"]):
        errors.append("observed_output must be a non-empty string")
    evidence = finding["evidence"]
    if not isinstance(evidence, list) or not evidence:
        return errors + ["evidence must be a non-empty array"]
    identities: list[str] = []
    for item in evidence:
        if not isinstance(item, dict) or set(item) != EVIDENCE_KEYS:
            errors.append("evidence keys must be exact")
            continue
        path, line, excerpt = item["path"], item["line"], item["excerpt"]
        if not _canonical_relative_path(path):
            errors.append("evidence path must be a safe relative path")
        if not _is_line(line):
            errors.append("evidence line must be a positive integer")
        elif _canonical_relative_path(path):
            identities.append(_portability_key(f"{path}:{line}"))
        if not _non_empty_string(excerpt):
            errors.append("evidence excerpt must be a non-empty string")
    if len(identities) != len(set(identities)):
        errors.append("evidence identities must be unique")
    return errors


def _finding_id(finding: object) -> str | None:
    if isinstance(finding, dict) and _non_empty_string(finding.get("finding_id")):
        return finding["finding_id"]
    return None


def _evidence_identities(finding: dict[str, Any]) -> list[str]:
    evidence = finding.get("evidence")
    if not isinstance(evidence, list):
        return []
    return [f"{item['path']}:{item['line']}" for item in evidence if isinstance(item, dict) and _canonical_relative_path(item.get("path")) and _is_line(item.get("line"))]


def _is_material_severity(value: object) -> bool:
    return value == "CRITICAL" or value == "MATERIAL"


def validate_packet(packet: object, case: object) -> list[str]:
    """Return deterministic validation errors for a packet and selected case."""
    case_errors = _case_errors(case)
    if case_errors:
        return case_errors
    assert isinstance(case, dict)
    if not isinstance(packet, dict) or set(packet) != PACKET_KEYS:
        return ["packet keys must be exact"]
    errors: list[str] = []
    status = packet["status"]
    if not isinstance(status, str) or status not in STATUSES:
        errors.append("status must be FINDINGS_REPORTED or CLEAN_CONTROL_PASS")
    findings = packet["findings"]
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []
    if status == "FINDINGS_REPORTED" and not findings:
        errors.append("FINDINGS_REPORTED requires non-empty findings")
    if status == "CLEAN_CONTROL_PASS" and findings:
        errors.append("CLEAN_CONTROL_PASS requires empty findings")
    for field in ("scope", "residual_risk"):
        if not _non_empty_string(packet[field]):
            errors.append(f"packet {field} must be a non-empty string")
    if packet["scope"] != case["case_id"]:
        errors.append("packet scope must exactly match case_id")
    finding_ids: set[str] = set()
    for finding in findings:
        errors.extend(_finding_errors(finding))
        finding_id = _finding_id(finding)
        if finding_id is not None:
            if finding_id in finding_ids:
                errors.append(f"duplicate finding id {finding_id}")
            finding_ids.add(finding_id)
    expected_ids = set(case["expected_finding_ids"])
    by_id = {finding_id: finding for finding in findings if (finding_id := _finding_id(finding)) is not None and isinstance(finding, dict)}
    for expected_id in sorted(expected_ids - set(by_id)):
        errors.append(f"missing expected finding {expected_id}")
    if case["clean_control"] is True:
        for finding_id, finding in by_id.items():
            if _is_material_severity(finding.get("severity")):
                errors.append(f"material false positive {finding_id}")
        return errors
    for expected_id in sorted(expected_ids & set(by_id)):
        finding = by_id[expected_id]
        if finding.get("dimension") != case["dimension"]:
            errors.append(f"dimension mismatch for {expected_id}")
        if finding.get("severity") != case["severity"]:
            errors.append(f"severity mismatch for {expected_id}")
        expected_identity = case["expected_evidence"][expected_id]
        if _evidence_identities(finding).count(expected_identity) != 1:
            errors.append(f"evidence mismatch for {expected_id}")
    for finding_id, finding in by_id.items():
        if finding_id not in expected_ids and _is_material_severity(finding.get("severity")):
            errors.append(f"unexpected material finding {finding_id}")
    return errors


def validate_catalog(catalog: object) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Validate frozen catalog identities without requiring fixture bytes to exist."""
    if not isinstance(catalog, dict) or set(catalog) != {"cases"}:
        return ["catalog keys must be exact"], {}
    cases = catalog["cases"]
    if not isinstance(cases, list):
        return ["catalog cases must be an array"], {}
    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        errors.extend(_case_errors(case))
        if isinstance(case, dict) and _non_empty_string(case.get("case_id")):
            case_id = case["case_id"]
            if case_id in by_id:
                errors.append(f"duplicate catalog case_id {case_id}")
            else:
                by_id[case_id] = case
    if len(cases) != 17 or set(by_id) != FROZEN_CASE_IDS:
        errors.append("catalog case IDs must match the frozen 17-case identity")
    for case_id, spec in FROZEN_CASE_SPECS.items():
        case = by_id.get(case_id)
        if case is None:
            continue
        root, dimension, severity, finding_ids, identities = spec
        listed_ids = case.get("expected_finding_ids")
        evidence = case.get("expected_evidence")
        actual_identities = (
            tuple(evidence.get(finding_id) for finding_id in listed_ids)
            if isinstance(listed_ids, list)
            and all(isinstance(finding_id, str) for finding_id in listed_ids)
            and isinstance(evidence, dict)
            else ()
        )
        if (
            case.get("project_root"), case.get("dimension"), case.get("severity"),
            tuple(listed_ids) if isinstance(listed_ids, list) and all(isinstance(item, str) for item in listed_ids) else (), actual_identities,
        ) != (root, dimension, severity, finding_ids, identities):
            errors.append(f"catalog frozen identity mismatch for {case_id}")
    if any(by_id.get(case_id, {}).get("dimension") != dimension for case_id, dimension in D_CASE_DIMENSIONS.items()):
        errors.append("D01-D12 catalog dimensions must be represented exactly once")
    clean_ids = {case_id for case_id, case in by_id.items() if case.get("clean_control") is True}
    if clean_ids != CLEAN_CASE_IDS:
        errors.append("catalog must contain exactly the three frozen clean controls")
    if len(MIXED_CASE_IDS & set(by_id)) != 2 or any(by_id.get(case_id, {}).get("clean_control") is True for case_id in MIXED_CASE_IDS):
        errors.append("catalog must contain exactly two non-clean mixed cases")
    expected_ids: set[str] = set()
    roots: set[str] = set()
    root_identities: set[str] = set()
    for case in by_id.values():
        root = case.get("project_root")
        if isinstance(root, str):
            portability_root = _portability_key(root)
            if portability_root in roots:
                errors.append("catalog project_root values must be unique")
            roots.add(portability_root)
        ids, evidence = case.get("expected_finding_ids"), case.get("expected_evidence")
        if case.get("clean_control") is not True and isinstance(ids, list) and not ids:
            errors.append("non-clean cases require expected findings")
        if isinstance(ids, list):
            for finding_id in ids:
                if isinstance(finding_id, str):
                    if finding_id in expected_ids:
                        errors.append("catalog expected finding IDs must be globally unique")
                    expected_ids.add(finding_id)
        if isinstance(root, str) and isinstance(evidence, dict):
            for identity in evidence.values():
                if isinstance(identity, str):
                    qualified = _portability_key(f"{root}/{identity}")
                    if qualified in root_identities:
                        errors.append("catalog root-qualified evidence identities must be unique")
                    root_identities.add(qualified)
    return errors, by_id


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _read_json(path_text: str, label: str) -> tuple[object | None, str | None]:
    try:
        with open(path_text, encoding="utf-8") as handle:
            return json.load(handle, object_pairs_hook=_unique_object, parse_constant=_reject_json_constant), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, f"{label} error: {exc}"


def _parse_flags(arguments: list[str]) -> tuple[dict[str, str] | None, str | None]:
    required = {"--packet", "--catalog", "--case"}
    if len(arguments) != 6 or set(arguments[::2]) != required:
        return None, "usage requires --packet PATH --catalog PATH --case CASE_ID"
    values = dict(zip(arguments[::2], arguments[1::2], strict=True))
    if any(not value for value in values.values()):
        return None, "usage flag values must be non-empty"
    return values, None


def main(arguments: list[str] | None = None) -> int:
    values, usage_error = _parse_flags(list(sys.argv[1:] if arguments is None else arguments))
    if usage_error is not None:
        print(json.dumps({"errors": [usage_error]}, separators=(",", ":")))
        return 2
    assert values is not None
    packet, packet_error = _read_json(values["--packet"], "packet")
    catalog, catalog_error = _read_json(values["--catalog"], "catalog")
    errors = [error for error in (packet_error, catalog_error) if error is not None]
    cases: dict[str, dict[str, Any]] = {}
    if catalog_error is None:
        catalog_errors, cases = validate_catalog(catalog)
        errors.extend(catalog_errors)
    case = cases.get(values["--case"])
    if case is None and catalog_error is None:
        errors.append(f"case not found: {values['--case']}")
    if packet_error is None and case is not None:
        errors.extend(validate_packet(packet, case))
    if errors:
        print(json.dumps({"errors": errors}, separators=(",", ":")))
        return 2
    print('{"status":"valid"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
