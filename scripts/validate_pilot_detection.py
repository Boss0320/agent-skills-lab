from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
import sys
from typing import Any
import unicodedata


RECORD_KEYS = {"material_finding", "summary", "evidence"}
EVIDENCE_KEYS = {"path", "line"}


class DetectionValidationError(ValueError):
    """Raised when pilot input cannot be decoded safely."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DetectionValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise DetectionValidationError(f"invalid JSON constant: {value}")


def _load_json(path: Path, label: str) -> Any:
    try:
        raw = path.read_bytes()
        if len(raw) > 1024 * 1024:
            raise DetectionValidationError(f"{label} is too large")
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        if isinstance(error, DetectionValidationError):
            raise
        raise DetectionValidationError(f"{label} unreadable: {error}") from error


def _is_single_line_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == unicodedata.normalize("NFC", value)
        and all(unicodedata.category(character) not in {"Cc", "Cf"} for character in value)
    )


def _is_canonical_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    path = Path(value)
    windows_path = PureWindowsPath(value)
    return (
        not path.is_absolute()
        and not windows_path.is_absolute()
        and not windows_path.drive
        and path != Path(".")
        and path.as_posix() == value
        and value == unicodedata.normalize("NFC", value)
        and all(part not in {"", ".", ".."} and not part.startswith(".") for part in path.parts)
        and all(unicodedata.category(character) not in {"Cc", "Cf"} for character in value)
    )


def _parse_anchor(value: str | None) -> tuple[str, int] | None:
    if value is None:
        return None
    path, separator, raw_line = value.rpartition(":")
    if not separator or not _is_canonical_relative_path(path):
        raise DetectionValidationError("expected evidence anchor is malformed")
    try:
        line = int(raw_line)
    except ValueError as error:
        raise DetectionValidationError("expected evidence anchor is malformed") from error
    if line <= 0 or str(line) != raw_line:
        raise DetectionValidationError("expected evidence anchor is malformed")
    return path, line


def validate_detection(
    record: object,
    expected_material: bool,
    expected_evidence: str | None,
) -> list[str]:
    """Validate the answer-neutral detection record against grader-only truth."""
    errors: list[str] = []
    if not isinstance(expected_material, bool):
        raise TypeError("expected_material must be a bool")
    anchor = _parse_anchor(expected_evidence)
    if (anchor is None) == expected_material:
        raise DetectionValidationError("grader expectation is internally inconsistent")

    if not isinstance(record, dict) or set(record) != RECORD_KEYS:
        return ["record keys must be exact"]

    material = record["material_finding"]
    summary = record["summary"]
    evidence = record["evidence"]
    if not isinstance(material, bool):
        errors.append("material_finding must be a bool")
    elif material != expected_material:
        errors.append("material_finding does not match the selected case")

    if material is False:
        if summary is not None:
            errors.append("clean summary must be null")
        if evidence != []:
            errors.append("clean evidence must be an empty list")
        return errors

    if not _is_single_line_text(summary):
        errors.append("summary must be a non-empty single-line string")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
        return errors

    identities: list[tuple[str, int]] = []
    anchor_count = 0
    for item in evidence:
        if not isinstance(item, dict) or set(item) != EVIDENCE_KEYS:
            errors.append("evidence item keys must be exact")
            continue
        path = item["path"]
        line = item["line"]
        path_valid = _is_canonical_relative_path(path)
        line_valid = isinstance(line, int) and not isinstance(line, bool) and line > 0
        if not path_valid:
            errors.append("evidence path must be a canonical relative path")
        if not line_valid:
            errors.append("evidence line must be a positive integer")
        if path_valid and line_valid:
            identity = (unicodedata.normalize("NFC", path).casefold(), line)
            identities.append(identity)
            if anchor is not None and (path, line) == anchor:
                anchor_count += 1

    if len(set(identities)) != len(identities):
        errors.append("evidence identities must be portable and unique")
    if anchor_count != 1:
        errors.append("expected evidence anchor must appear exactly once")
    return errors


def _case_expectation(catalog: object, case_id: str) -> tuple[bool, str | None]:
    if not isinstance(catalog, dict) or set(catalog) != {"cases"} or not isinstance(catalog["cases"], list):
        raise DetectionValidationError("catalog shape is invalid")
    matches = [case for case in catalog["cases"] if isinstance(case, dict) and case.get("case_id") == case_id]
    if len(matches) != 1:
        raise DetectionValidationError("selected case must appear exactly once")
    selected = matches[0]
    clean = selected.get("clean_control")
    finding_ids = selected.get("expected_finding_ids")
    evidence = selected.get("expected_evidence")
    if not isinstance(clean, bool) or not isinstance(finding_ids, list) or not isinstance(evidence, dict):
        raise DetectionValidationError("selected case expectation is invalid")
    if clean:
        if finding_ids or evidence:
            raise DetectionValidationError("clean case expectation is not closed")
        return False, None
    if len(finding_ids) != 1 or set(evidence) != {finding_ids[0]} or not isinstance(evidence[finding_ids[0]], str):
        raise DetectionValidationError("pilot positive case must have one bound finding")
    return True, evidence[finding_ids[0]]


def _parse_arguments(arguments: list[str]) -> tuple[Path, Path, str] | None:
    if len(arguments) != 6:
        return None
    values: dict[str, str] = {}
    for index in range(0, len(arguments), 2):
        flag, value = arguments[index], arguments[index + 1]
        if flag not in {"--record", "--catalog", "--case"} or flag in values or not value or value.startswith("-"):
            return None
        values[flag] = value
    if set(values) != {"--record", "--catalog", "--case"}:
        return None
    return Path(values["--record"]), Path(values["--catalog"]), values["--case"]


def main(arguments: list[str] | None = None) -> int:
    parsed = _parse_arguments(list(sys.argv[1:] if arguments is None else arguments))
    if parsed is None:
        print(json.dumps({"errors": ["usage requires --record PATH --catalog PATH --case CASE_ID"]}, separators=(",", ":")))
        return 2
    record_path, catalog_path, case_id = parsed
    try:
        record = _load_json(record_path, "record")
        catalog = _load_json(catalog_path, "catalog")
        expected_material, expected_evidence = _case_expectation(catalog, case_id)
        errors = validate_detection(record, expected_material, expected_evidence)
    except (DetectionValidationError, TypeError) as error:
        errors = [str(error)]
    if errors:
        print(json.dumps({"errors": errors}, separators=(",", ":"), sort_keys=True))
        return 2
    print(json.dumps({"status": "valid"}, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
