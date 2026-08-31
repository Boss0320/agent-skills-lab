from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


CONFIGURATIONS = ("with_skill", "without_skill")
_RESULT_INTEGER_FIELDS = ("passed", "failed", "total", "tokens", "errors")
_PACKET_KEYS = {"metadata", "runs", "run_summary", "limitations", "claims"}
_METADATA_KEYS = {
    "skill_name",
    "skill_sha256",
    "executor_model",
    "surface",
    "timestamp",
    "evals_run",
    "runs_per_configuration",
    "fixture_sha256",
}
_RUN_KEYS = {"eval_id", "eval_name", "configuration", "run_number", "result", "expectations"}
_RESULT_KEYS = {"pass_rate", "passed", "failed", "total", "time_seconds", "tokens", "errors"}
_SUMMARY_KEYS = {"with_skill", "without_skill", "delta"}
_CLAIM_KEYS = {"claim", "metric", "operator", "threshold"}
_METRIC_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_METRIC_REFERENCE = re.compile(r"^(with_skill|without_skill|delta)\.([A-Za-z][A-Za-z0-9_]*)$")
_CLAIM_OPERATORS = {">=", "<=", ">", "<", "=="}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for the exact bytes stored at *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    if _is_integer(value):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value)


def _append_unknown_key_errors(
    value: dict[Any, Any], allowed_keys: set[str], prefix: str, errors: list[str]
) -> None:
    for key in sorted(set(value) - allowed_keys, key=str):
        errors.append(f"{prefix}.{key} is not allowed")


def _append_metadata_errors(
    metadata: dict[str, Any], errors: list[str]
) -> tuple[set[int], int | None, set[str]]:
    _append_unknown_key_errors(metadata, _METADATA_KEYS, "metadata", errors)
    for key in ("skill_name", "executor_model", "surface", "timestamp"):
        if not _is_non_empty_string(metadata.get(key)):
            errors.append(f"metadata.{key} must be a non-empty string")
    timestamp = metadata.get("timestamp")
    if _is_non_empty_string(timestamp):
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            errors.append("metadata.timestamp must be ISO-8601")
    if not _is_sha256(metadata.get("skill_sha256")):
        errors.append("metadata.skill_sha256 must be a SHA-256 digest")

    evals_run = metadata.get("evals_run")
    eval_ids: set[int] = set()
    if not isinstance(evals_run, list) or not evals_run:
        errors.append("metadata.evals_run must be a non-empty list of positive integers")
    elif any(not _is_integer(value) or value <= 0 for value in evals_run):
        errors.append("metadata.evals_run must be a non-empty list of positive integers")
    elif len(set(evals_run)) != len(evals_run):
        errors.append("metadata.evals_run must not contain duplicates")
    else:
        eval_ids = set(evals_run)

    repetitions = metadata.get("runs_per_configuration")
    if not _is_integer(repetitions) or repetitions <= 0:
        errors.append("metadata.runs_per_configuration must be a positive integer")
        repetitions = None

    fixture_digests = metadata.get("fixture_sha256")
    fixture_names: set[str] = set()
    if not isinstance(fixture_digests, dict) or not fixture_digests:
        errors.append("metadata.fixture_sha256 must be a non-empty object")
    else:
        for name, digest in fixture_digests.items():
            if not _is_non_empty_string(name):
                errors.append("metadata.fixture_sha256 keys must be non-empty strings")
            else:
                fixture_names.add(name)
            if not _is_sha256(digest):
                errors.append(f"metadata.fixture_sha256.{name} must be a SHA-256 digest")
    return eval_ids, repetitions, fixture_names


def _append_result_errors(result: Any, prefix: str, errors: list[str]) -> None:
    if not isinstance(result, dict):
        errors.append(f"{prefix} must be an object")
        return
    _append_unknown_key_errors(result, _RESULT_KEYS, prefix, errors)
    for key in _RESULT_INTEGER_FIELDS:
        value = result.get(key)
        if not _is_integer(value) or value < 0:
            errors.append(f"{prefix}.{key} must be a non-negative integer")
    total = result.get("total")
    if _is_integer(total) and total <= 0:
        errors.append(f"{prefix}.total must be greater than zero")
    pass_rate = result.get("pass_rate")
    valid_pass_rate = _is_number(pass_rate) and 0.0 <= pass_rate <= 1.0
    if not valid_pass_rate:
        errors.append(f"{prefix}.pass_rate must be a finite number from 0 to 1")
    time_seconds = result.get("time_seconds")
    if not _is_number(time_seconds) or time_seconds < 0:
        errors.append(f"{prefix}.time_seconds must be a finite non-negative number")
    errors_count = result.get("errors")
    if _is_integer(errors_count) and _is_integer(total) and errors_count > total:
        errors.append(f"{prefix}.errors must not exceed total")
    counter_keys = ("passed", "failed", "total")
    integer_counters = all(_is_integer(result.get(key)) for key in counter_keys)
    valid_counters = all(
        _is_integer(result.get(key)) and result[key] >= 0 for key in counter_keys
    )
    matching_total = False
    if integer_counters:
        passed = result["passed"]
        failed = result["failed"]
        matching_total = passed + failed == total
        if not matching_total:
            errors.append(f"{prefix}.passed + failed must equal total")
    if valid_counters:
        if valid_pass_rate and matching_total and total > 0 and not math.isclose(
            pass_rate, passed / total, rel_tol=0.0, abs_tol=1e-12
        ):
            errors.append(f"{prefix}.pass_rate must equal passed / total")


def _resolve_summary_metric(summary: dict[str, Any], metric: str) -> Any | None:
    match = _METRIC_REFERENCE.fullmatch(metric)
    if match is None:
        return None
    section = summary.get(match.group(1))
    if not isinstance(section, dict):
        return None
    return section.get(match.group(2))


def _normalized_claim(metric: str, operator: str, threshold: int | float) -> str:
    return f"{metric} {operator} {json.dumps(threshold, allow_nan=False)}"


def _claim_is_true(value: int | float, operator: str, threshold: int | float) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    return value == threshold


def validate_evidence_packet(
    packet: dict[str, Any], expected_skill_id: str | None = None
) -> list[str]:
    """Return stable, consumer-facing validation errors for an evidence packet."""
    if not isinstance(packet, dict):
        return ["packet must be an object"]

    errors: list[str] = []
    _append_unknown_key_errors(packet, _PACKET_KEYS, "packet", errors)
    metadata = packet.get("metadata")
    if not isinstance(metadata, dict):
        return ["metadata must be an object"]
    if expected_skill_id is not None and metadata.get("skill_name") != expected_skill_id:
        errors.append("metadata.skill_name does not match expected skill")
    eval_ids, repetitions, fixture_names = _append_metadata_errors(metadata, errors)

    runs = packet.get("runs")
    seen_runs: set[tuple[int, str, int]] = set()
    run_names_by_id: dict[int, set[str]] = {}
    if not isinstance(runs, list) or not runs:
        errors.append("runs must be a non-empty list")
    else:
        for index, run in enumerate(runs):
            prefix = f"runs[{index}]"
            if not isinstance(run, dict):
                errors.append(f"{prefix} must be an object")
                continue
            _append_unknown_key_errors(run, _RUN_KEYS, prefix, errors)
            eval_id = run.get("eval_id")
            if not _is_integer(eval_id) or eval_id not in eval_ids:
                errors.append(f"{prefix}.eval_id must be listed in metadata.evals_run")
            eval_name = run.get("eval_name")
            if not _is_non_empty_string(eval_name) or eval_name not in fixture_names:
                errors.append(f"{prefix}.eval_name must have a fixture digest")
            elif _is_integer(eval_id):
                run_names_by_id.setdefault(eval_id, set()).add(eval_name)
            configuration = run.get("configuration")
            if configuration not in CONFIGURATIONS:
                errors.append(f"{prefix}.configuration is invalid")
            run_number = run.get("run_number")
            if (
                repetitions is None
                or not _is_integer(run_number)
                or not 1 <= run_number <= repetitions
            ):
                errors.append(f"{prefix}.run_number is outside the declared repetitions")
            if (
                _is_integer(eval_id)
                and eval_id in eval_ids
                and configuration in CONFIGURATIONS
                and _is_integer(run_number)
                and repetitions is not None
                and 1 <= run_number <= repetitions
            ):
                identity = (eval_id, configuration, run_number)
                if identity in seen_runs:
                    errors.append(f"{prefix} duplicates a paired run")
                seen_runs.add(identity)
            _append_result_errors(run.get("result"), f"{prefix}.result", errors)
            if not isinstance(run.get("expectations"), list):
                errors.append(f"{prefix}.expectations must be a list")

    if repetitions is not None:
        for eval_id in sorted(eval_ids):
            for configuration in CONFIGURATIONS:
                for run_number in range(1, repetitions + 1):
                    if (eval_id, configuration, run_number) not in seen_runs:
                        errors.append(
                            "missing paired run for "
                            f"eval_id {eval_id}, configuration {configuration}, "
                            f"run_number {run_number}"
                        )
    observed_fixture_names = set().union(*run_names_by_id.values()) if run_names_by_id else set()
    for eval_id in sorted(eval_ids):
        if len(run_names_by_id.get(eval_id, set())) != 1:
            errors.append(f"eval_id {eval_id} must have exactly one eval_name")
    for name in sorted(fixture_names - observed_fixture_names):
        errors.append(f"metadata.fixture_sha256.{name} is not referenced by a run")

    summary = packet.get("run_summary")
    if not isinstance(summary, dict):
        errors.append("run_summary must be an object")
        summary = {}
    _append_unknown_key_errors(summary, _SUMMARY_KEYS, "run_summary", errors)
    for key in ("with_skill", "without_skill", "delta"):
        if key not in summary:
            errors.append(f"run_summary.{key} is required")
        elif not isinstance(summary[key], dict):
            errors.append(f"run_summary.{key} must be an object")
        else:
            for metric_name, value in summary[key].items():
                metric_prefix = f"run_summary.{key}.{metric_name}"
                if not isinstance(metric_name, str) or _METRIC_NAME.fullmatch(metric_name) is None:
                    errors.append(f"{metric_prefix} is not a safe metric name")
                if not _is_number(value):
                    errors.append(f"{metric_prefix} must be a finite number")

    limitations = packet.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        errors.append("limitations must be a non-empty list")
    elif any(not _is_non_empty_string(item) for item in limitations):
        errors.append("limitations entries must be non-empty strings")

    claims = packet.get("claims")
    if not isinstance(claims, list):
        errors.append("claims must be a list")
    else:
        for index, claim in enumerate(claims):
            prefix = f"claims[{index}]"
            if not isinstance(claim, dict):
                errors.append(f"{prefix} must be an object")
                continue
            _append_unknown_key_errors(claim, _CLAIM_KEYS, prefix, errors)
            for key in ("claim", "metric", "operator"):
                if not _is_non_empty_string(claim.get(key)):
                    errors.append(f"{prefix}.{key} must be a non-empty string")
            threshold = claim.get("threshold")
            if not _is_number(threshold):
                errors.append(f"{prefix}.threshold must be a finite number")
            metric = claim.get("metric")
            operator = claim.get("operator")
            if _is_non_empty_string(operator) and operator not in _CLAIM_OPERATORS:
                errors.append(f"{prefix}.operator is invalid")
            if _is_non_empty_string(metric) and _METRIC_REFERENCE.fullmatch(metric) is None:
                errors.append(f"{prefix}.metric is invalid")
            valid_claim_expression = (
                _is_non_empty_string(metric)
                and _METRIC_REFERENCE.fullmatch(metric) is not None
                and _is_non_empty_string(operator)
                and operator in _CLAIM_OPERATORS
                and _is_number(threshold)
            )
            if valid_claim_expression:
                normalized = _normalized_claim(metric, operator, threshold)
                if claim.get("claim") != normalized:
                    errors.append(f"{prefix}.claim must equal {normalized!r}")
            if _is_non_empty_string(metric):
                value = _resolve_summary_metric(summary, metric)
                if not _is_number(value):
                    errors.append(f"{prefix}.metric must reference a numeric run_summary value")
                elif valid_claim_expression:
                    if not _claim_is_true(value, operator, threshold):
                        errors.append(f"{prefix} condition is false")
    return errors


def _write_response(errors: list[str]) -> None:
    print(json.dumps({"errors": errors}, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--help"] or arguments == ["-h"]:
        _write_response(["usage: verify_evidence_packet.py PACKET [--expected-skill-id SKILL_ID]"])
        return 2
    invalid_shape = len(arguments) not in (1, 3)
    invalid_option = len(arguments) == 3 and arguments[1] != "--expected-skill-id"
    if invalid_shape or invalid_option:
        _write_response(["usage: verify_evidence_packet.py PACKET [--expected-skill-id SKILL_ID]"])
        return 2
    path = Path(arguments[0])
    expected_skill_id = arguments[2] if len(arguments) == 3 else None
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        _write_response(["input could not be read"])
        return 2
    except UnicodeDecodeError:
        _write_response(["input is not valid UTF-8"])
        return 2
    except (json.JSONDecodeError, ValueError):
        _write_response(["input is not valid JSON"])
        return 2
    errors = validate_evidence_packet(packet, expected_skill_id)
    _write_response(errors)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
