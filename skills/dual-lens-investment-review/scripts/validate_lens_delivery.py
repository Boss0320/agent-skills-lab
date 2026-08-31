from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


DECISION_KEYS = {
    "case_id",
    "lens",
    "disposition",
    "material_failure",
    "primary_claim_id",
    "primary_category",
}
FILE_NAMES = {"lens-decision.json", "lens-review.json"}


def _load_reconciler() -> Any:
    path = Path(__file__).with_name("reconcile_reviews.py")
    spec = importlib.util.spec_from_file_location("dual_lens_reconciler", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load review validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECONCILER = _load_reconciler()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _unavailable(
    expected_case_id: str,
    expected_lens: str,
    errors: list[dict[str, str]],
    combined_bytes: int = 0,
) -> dict[str, object]:
    return {
        "execution_state": "UNAVAILABLE",
        "case_id": expected_case_id,
        "lens": expected_lens,
        "combined_bytes": combined_bytes,
        "errors": errors,
    }


def _validate_decision(decision: object, expected_lens: str) -> list[dict[str, str]]:
    if not isinstance(decision, dict) or set(decision) != DECISION_KEYS:
        return [_error("DECISION_SCHEMA_INVALID", "lens-decision.json keys mismatch")]
    errors: list[dict[str, str]] = []
    if not isinstance(decision["case_id"], str) or not decision["case_id"].strip():
        errors.append(_error("DECISION_SCHEMA_INVALID", "case_id must be a non-empty string"))
    if decision["lens"] != expected_lens:
        errors.append(_error("LENS_MISMATCH", "decision lens does not match expected lens"))
    disposition = decision["disposition"]
    material_failure = decision["material_failure"]
    primary_claim_id = decision["primary_claim_id"]
    primary_category = decision["primary_category"]
    if disposition not in RECONCILER.DISPOSITIONS:
        errors.append(_error("DECISION_SCHEMA_INVALID", "disposition is invalid"))
        return errors
    if not isinstance(material_failure, bool):
        errors.append(_error("DECISION_SCHEMA_INVALID", "material_failure must be Boolean"))
    if disposition == "PASS":
        if material_failure is not False or primary_claim_id is not None or primary_category is not None:
            errors.append(_error("DECISION_RELATIONSHIP_INVALID", "PASS requires false materiality and null primary fields"))
    else:
        categories = (
            RECONCILER.USABILITY_CATEGORIES
            if expected_lens == "decision_usability"
            else RECONCILER.INTEGRITY_CATEGORIES
        )
        if material_failure is not (disposition == "BLOCK"):
            errors.append(_error("DECISION_RELATIONSHIP_INVALID", "disposition and material_failure disagree"))
        if not isinstance(primary_claim_id, str) or not primary_claim_id.strip():
            errors.append(_error("DECISION_SCHEMA_INVALID", "non-passing decision requires primary_claim_id"))
        if primary_category not in categories:
            errors.append(_error("DECISION_SCHEMA_INVALID", "primary_category is invalid for the lens"))
    return errors


def _primary_matches(decision: dict[str, object], review: dict[str, object]) -> bool:
    if not DECISION_KEYS.issubset(decision):
        return False
    if decision["disposition"] == "PASS":
        return True
    claim_id = decision["primary_claim_id"]
    category = decision["primary_category"]
    findings = review.get("findings")
    if not isinstance(findings, list):
        return False
    return any(
        isinstance(finding, dict)
        and finding.get("category") == category
        and isinstance(finding.get("claim_ids"), list)
        and claim_id in finding["claim_ids"]
        for finding in findings
    )


def validate_delivery(
    decision: object,
    review: object,
    *,
    expected_case_id: str,
    expected_lens: str,
    max_bytes: int,
    observed_bytes: int | None = None,
) -> dict[str, object]:
    if expected_lens not in RECONCILER.LENSES:
        return _unavailable(
            expected_case_id,
            expected_lens,
            [_error("EXPECTED_LENS_INVALID", "expected lens is invalid")],
        )
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        return _unavailable(
            expected_case_id,
            expected_lens,
            [_error("BYTE_LIMIT_INVALID", "max_bytes must be a positive integer")],
        )
    try:
        canonical = {
            "lens-decision.json": _canonical_bytes(decision),
            "lens-review.json": _canonical_bytes(review),
        }
    except (TypeError, ValueError) as error:
        return _unavailable(
            expected_case_id,
            expected_lens,
            [_error("JSON_VALUE_INVALID", str(error))],
        )
    combined_bytes = observed_bytes if observed_bytes is not None else sum(map(len, canonical.values()))
    errors = _validate_decision(decision, expected_lens)
    review_errors = RECONCILER.validate_review(review, expected_lens)
    errors.extend(_error("REVIEW_SCHEMA_INVALID", item) for item in review_errors)
    if isinstance(decision, dict):
        if decision.get("case_id") != expected_case_id:
            errors.append(_error("CASE_ID_MISMATCH", "decision case_id does not match expected case"))
        if decision.get("lens") != expected_lens and not any(item["code"] == "LENS_MISMATCH" for item in errors):
            errors.append(_error("LENS_MISMATCH", "decision lens does not match expected lens"))
    if isinstance(review, dict):
        if review.get("case_id") != expected_case_id:
            errors.append(_error("CASE_ID_MISMATCH", "review case_id does not match expected case"))
        if review.get("lens") != expected_lens:
            errors.append(_error("LENS_MISMATCH", "review lens does not match expected lens"))
    if isinstance(decision, dict) and isinstance(review, dict):
        pair_fields = ("case_id", "lens", "disposition", "material_failure")
        if any(decision.get(field) != review.get(field) for field in pair_fields):
            errors.append(_error("PAIR_DISAGREEMENT", "decision and detailed review disagree"))
        if not _primary_matches(decision, review):
            errors.append(_error("PRIMARY_FINDING_MISMATCH", "primary claim/category is not supported by a detailed finding"))
    if combined_bytes > max_bytes:
        errors.append(_error("OUTPUT_TOO_LARGE", f"combined output is {combined_bytes} bytes; limit is {max_bytes}"))
    if errors:
        return _unavailable(expected_case_id, expected_lens, errors, combined_bytes)
    assert isinstance(decision, dict)
    assert isinstance(review, dict)
    files = {"lens-decision.json": decision, "lens-review.json": review}
    return {
        "execution_state": "AVAILABLE",
        "case_id": expected_case_id,
        "lens": expected_lens,
        "files": files,
        "sha256": {name: hashlib.sha256(payload).hexdigest() for name, payload in canonical.items()},
        "combined_bytes": combined_bytes,
        "errors": [],
    }


def validate_capture(
    envelope: object,
    *,
    expected_case_id: str,
    expected_lens: str,
    max_bytes: int,
    observed_bytes: int | None = None,
) -> dict[str, object]:
    if not isinstance(envelope, dict) or set(envelope) != {"files"}:
        return _unavailable(
            expected_case_id,
            expected_lens,
            [_error("CAPTURE_SCHEMA_INVALID", "capture must contain only the files object")],
            observed_bytes or 0,
        )
    files = envelope["files"]
    if not isinstance(files, dict) or set(files) != FILE_NAMES:
        return _unavailable(
            expected_case_id,
            expected_lens,
            [_error("CAPTURE_INCOMPLETE", "capture must contain exactly both lens files")],
            observed_bytes or 0,
        )
    return validate_delivery(
        files["lens-decision.json"],
        files["lens-review.json"],
        expected_case_id=expected_case_id,
        expected_lens=expected_lens,
        max_bytes=max_bytes,
        observed_bytes=observed_bytes,
    )


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, max_bytes: int) -> tuple[object, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input is not a regular non-symlink file: {path}")
    payload = path.read_bytes()
    if len(payload) > max_bytes:
        raise ValueError(f"input exceeds {max_bytes} bytes")
    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_pairs_no_duplicates,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"invalid JSON constant: {token}")),
    )
    return value, len(payload)


def _emit(result: dict[str, object]) -> None:
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(add_help=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--case", dest="case_id", required=True)
    parser.add_argument("--lens", required=True)
    parser.add_argument("--max-bytes", type=int, default=6000)
    try:
        args = parser.parse_args(argv)
        capture_mode = args.capture is not None and args.decision is None and args.review is None
        direct_mode = args.capture is None and args.decision is not None and args.review is not None
        if capture_mode == direct_mode:
            raise ValueError("select exactly one delivery mode: capture or decision+review")
        if args.max_bytes <= 0:
            raise ValueError("max-bytes must be positive")
        if capture_mode:
            envelope, observed_bytes = _read_json(args.capture, args.max_bytes)
            result = validate_capture(
                envelope,
                expected_case_id=args.case_id,
                expected_lens=args.lens,
                max_bytes=args.max_bytes,
                observed_bytes=observed_bytes,
            )
        else:
            decision, decision_bytes = _read_json(args.decision, args.max_bytes)
            review, review_bytes = _read_json(args.review, args.max_bytes)
            result = validate_delivery(
                decision,
                review,
                expected_case_id=args.case_id,
                expected_lens=args.lens,
                max_bytes=args.max_bytes,
                observed_bytes=decision_bytes + review_bytes,
            )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
        case_id = getattr(locals().get("args", None), "case_id", "UNKNOWN")
        lens = getattr(locals().get("args", None), "lens", "UNKNOWN")
        result = _unavailable(case_id, lens, [_error("INPUT_OR_USAGE_INVALID", str(error))])
        _emit(result)
        return 2
    _emit(result)
    return 0 if result["execution_state"] == "AVAILABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
