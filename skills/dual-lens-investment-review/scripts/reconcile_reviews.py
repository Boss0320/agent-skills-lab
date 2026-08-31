from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import unicodedata


COMMON_KEYS = {
    "case_id",
    "lens",
    "disposition",
    "material_failure",
    "findings",
    "residual_risk",
}
INTEGRITY_KEYS = {*COMMON_KEYS, "claim_checks"}
FINDING_KEYS = {"finding_id", "severity", "category", "claim_ids", "summary", "evidence"}
EVIDENCE_KEYS = {"path", "line", "excerpt"}
CLAIM_CHECK_KEYS = {"claim_id", "status", "material", "source_refs"}
LENSES = {"decision_usability", "source_integrity"}
DISPOSITIONS = {"PASS", "REVISE", "BLOCK"}
SEVERITIES = {"MATERIAL", "MINOR"}
CLAIM_STATUSES = {"SUPPORTED", "CONTRADICTED", "UNKNOWN"}
DECISION_KEYS = {
    "case_id",
    "lens",
    "disposition",
    "material_failure",
    "primary_claim_id",
    "primary_category",
}
DELIVERY_KEYS = {
    "execution_state",
    "case_id",
    "lens",
    "files",
    "sha256",
    "combined_bytes",
    "errors",
}
USABILITY_CATEGORIES = {
    "THESIS",
    "CATALYST",
    "RISK",
    "VALUATION",
    "CONTRADICTION",
    "UNKNOWN_HANDLING",
    "DECISION_FRAME",
}
INTEGRITY_CATEGORIES = {
    "SOURCE_SUPPORT",
    "PERIOD",
    "UNIT",
    "BASIS",
    "VALUATION_MEANING",
    "UNKNOWN_HANDLING",
    "INTERNAL_CONTRADICTION",
}


def _safe_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not any(
            character != "\n" and unicodedata.category(character) in {"Cc", "Cf"}
            for character in value
        )
    )


def _safe_relative_path(value: object) -> bool:
    if not _safe_string(value):
        return False
    path = Path(value)
    return not path.is_absolute() and "." not in path.parts and ".." not in path.parts


def _validate_evidence(items: object, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list) or not items:
        return [f"{prefix}.evidence must be a non-empty array"]
    identities: set[tuple[str, int]] = set()
    for index, item in enumerate(items):
        item_prefix = f"{prefix}.evidence[{index}]"
        if not isinstance(item, dict) or set(item) != EVIDENCE_KEYS:
            errors.append(f"{item_prefix} keys mismatch")
            continue
        if not _safe_relative_path(item["path"]):
            errors.append(f"{item_prefix}.path invalid")
        line = item["line"]
        if isinstance(line, bool) or not isinstance(line, int) or line <= 0:
            errors.append(f"{item_prefix}.line invalid")
            continue
        if not _safe_string(item["excerpt"]):
            errors.append(f"{item_prefix}.excerpt invalid")
        identity = (str(item["path"]), line)
        if identity in identities:
            errors.append(f"{item_prefix} duplicate identity")
        identities.add(identity)
    return errors


def _validate_findings(findings: object, lens: str) -> list[str]:
    if not isinstance(findings, list):
        return [f"{lens}.findings must be an array"]
    errors: list[str] = []
    finding_ids: set[str] = set()
    categories = USABILITY_CATEGORIES if lens == "decision_usability" else INTEGRITY_CATEGORIES
    for index, finding in enumerate(findings):
        prefix = f"{lens}.findings[{index}]"
        if not isinstance(finding, dict) or set(finding) != FINDING_KEYS:
            errors.append(f"{prefix} keys mismatch")
            continue
        finding_id = finding["finding_id"]
        if not _safe_string(finding_id) or finding_id in finding_ids:
            errors.append(f"{prefix}.finding_id invalid or duplicate")
        else:
            finding_ids.add(finding_id)
        if finding["severity"] not in SEVERITIES:
            errors.append(f"{prefix}.severity invalid")
        if finding["category"] not in categories:
            errors.append(f"{prefix}.category invalid")
        claim_ids = finding["claim_ids"]
        if (
            not isinstance(claim_ids, list)
            or not claim_ids
            or any(not _safe_string(item) for item in claim_ids)
            or len(claim_ids) != len(set(claim_ids))
        ):
            errors.append(f"{prefix}.claim_ids invalid")
        if not _safe_string(finding["summary"]):
            errors.append(f"{prefix}.summary invalid")
        errors.extend(_validate_evidence(finding["evidence"], prefix))
    return errors


def _validate_claim_checks(checks: object) -> list[str]:
    if not isinstance(checks, list) or not checks:
        return ["source_integrity.claim_checks must be a non-empty array"]
    errors: list[str] = []
    claim_ids: set[str] = set()
    for index, check in enumerate(checks):
        prefix = f"source_integrity.claim_checks[{index}]"
        if not isinstance(check, dict) or set(check) != CLAIM_CHECK_KEYS:
            errors.append(f"{prefix} keys mismatch")
            continue
        claim_id = check["claim_id"]
        if not _safe_string(claim_id) or claim_id in claim_ids:
            errors.append(f"{prefix}.claim_id invalid or duplicate")
        else:
            claim_ids.add(claim_id)
        if check["status"] not in CLAIM_STATUSES:
            errors.append(f"{prefix}.status invalid")
        if not isinstance(check["material"], bool):
            errors.append(f"{prefix}.material invalid")
        errors.extend(_validate_evidence(check["source_refs"], prefix))
    return errors


def validate_review(review: object, expected_lens: str) -> list[str]:
    if expected_lens not in LENSES:
        raise ValueError("expected_lens is invalid")
    if not isinstance(review, dict):
        return [f"{expected_lens} review must be an object"]
    expected_keys = INTEGRITY_KEYS if expected_lens == "source_integrity" else COMMON_KEYS
    errors: list[str] = []
    if set(review) != expected_keys:
        return [f"{expected_lens} keys mismatch"]
    if not _safe_string(review["case_id"]):
        errors.append(f"{expected_lens}.case_id invalid")
    if review["lens"] != expected_lens:
        errors.append(f"{expected_lens}.lens mismatch")
    disposition = review["disposition"]
    material_failure = review["material_failure"]
    if disposition not in DISPOSITIONS:
        errors.append(f"{expected_lens}.disposition invalid")
    if not isinstance(material_failure, bool):
        errors.append(f"{expected_lens}.material_failure invalid")
    errors.extend(_validate_findings(review["findings"], expected_lens))
    if not _safe_string(review["residual_risk"]):
        errors.append(f"{expected_lens}.residual_risk invalid")
    if expected_lens == "source_integrity":
        errors.extend(_validate_claim_checks(review["claim_checks"]))
    if disposition == "PASS" and (material_failure is not False or review["findings"]):
        errors.append(f"{expected_lens} PASS relationship invalid")
    if disposition == "REVISE" and (material_failure is not False or not review["findings"]):
        errors.append(f"{expected_lens} REVISE relationship invalid")
    if disposition == "BLOCK" and (material_failure is not True or not review["findings"]):
        errors.append(f"{expected_lens} BLOCK relationship invalid")
    material_findings = any(
        isinstance(finding, dict) and finding.get("severity") == "MATERIAL"
        for finding in review["findings"]
    )
    if expected_lens == "source_integrity" and isinstance(review["claim_checks"], list):
        non_supported = [
            check
            for check in review["claim_checks"]
            if isinstance(check, dict) and check.get("status") in {"CONTRADICTED", "UNKNOWN"}
        ]
        material_claim_issue = any(check.get("material") is True for check in non_supported)
        check_by_claim = {
            check.get("claim_id"): check
            for check in review["claim_checks"]
            if isinstance(check, dict) and _safe_string(check.get("claim_id"))
        }
        for finding in review["findings"]:
            if not isinstance(finding, dict) or not isinstance(finding.get("claim_ids"), list):
                continue
            related_issues = [
                check_by_claim[claim_id]
                for claim_id in finding["claim_ids"]
                if claim_id in check_by_claim
                and check_by_claim[claim_id].get("status") in {"CONTRADICTED", "UNKNOWN"}
            ]
            if not related_issues:
                errors.append("source_integrity finding has no matching non-supported claim check")
            elif finding.get("severity") == "MATERIAL" and not any(
                check.get("material") is True for check in related_issues
            ):
                errors.append("source_integrity MATERIAL finding lacks a material claim issue")
            elif finding.get("severity") == "MINOR" and any(
                check.get("material") is True for check in related_issues
            ):
                errors.append("source_integrity MINOR finding hides a material claim issue")
        if disposition == "PASS" and non_supported:
            errors.append("source_integrity claim_checks relationship invalid")
        if disposition == "REVISE" and material_claim_issue:
            errors.append("source_integrity claim_checks relationship invalid")
        if disposition == "BLOCK" and not material_claim_issue:
            errors.append("source_integrity claim_checks relationship invalid")
    elif disposition == "BLOCK" and not material_findings:
        errors.append("decision_usability findings relationship invalid")
    elif disposition == "REVISE" and material_findings:
        errors.append("decision_usability findings relationship invalid")
    return errors


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_size(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _review_from_available_delivery(delivery: object, expected_lens: str) -> dict[str, object]:
    if not isinstance(delivery, dict) or set(delivery) != DELIVERY_KEYS:
        raise ValueError(f"{expected_lens} delivery keys mismatch")
    if delivery["execution_state"] != "AVAILABLE" or delivery["errors"] != []:
        raise ValueError(f"{expected_lens} delivery is not AVAILABLE")
    if delivery["lens"] != expected_lens:
        raise ValueError(f"{expected_lens} delivery lens mismatch")
    if (
        isinstance(delivery["combined_bytes"], bool)
        or not isinstance(delivery["combined_bytes"], int)
        or delivery["combined_bytes"] <= 0
        or delivery["combined_bytes"] > 6000
    ):
        raise ValueError(f"{expected_lens} delivery byte count invalid")
    files = delivery["files"]
    digests = delivery["sha256"]
    expected_files = {"lens-decision.json", "lens-review.json"}
    if not isinstance(files, dict) or set(files) != expected_files:
        raise ValueError(f"{expected_lens} delivery files mismatch")
    if not isinstance(digests, dict) or set(digests) != expected_files:
        raise ValueError(f"{expected_lens} delivery digest keys mismatch")
    for name in expected_files:
        if digests[name] != _digest(files[name]):
            raise ValueError(f"{expected_lens} delivery digest mismatch for {name}")
    if sum(_canonical_size(files[name]) for name in expected_files) > delivery["combined_bytes"]:
        raise ValueError(f"{expected_lens} delivery byte count is smaller than its content")
    decision = files["lens-decision.json"]
    review = files["lens-review.json"]
    review_errors = validate_review(review, expected_lens)
    if review_errors:
        raise ValueError("; ".join(review_errors))
    if not isinstance(decision, dict) or set(decision) != DECISION_KEYS:
        raise ValueError(f"{expected_lens} decision keys mismatch")
    assert isinstance(review, dict)
    if delivery["case_id"] != review["case_id"] or delivery["case_id"] != decision["case_id"]:
        raise ValueError(f"{expected_lens} delivery case_id mismatch")
    if decision["lens"] != expected_lens:
        raise ValueError(f"{expected_lens} decision lens mismatch")
    if any(
        decision[field] != review[field]
        for field in ("case_id", "lens", "disposition", "material_failure")
    ):
        raise ValueError(f"{expected_lens} decision and review disagree")
    if decision["disposition"] == "PASS":
        if decision["primary_claim_id"] is not None or decision["primary_category"] is not None:
            raise ValueError(f"{expected_lens} PASS primary fields must be null")
    else:
        if not any(
            isinstance(finding, dict)
            and finding.get("category") == decision["primary_category"]
            and decision["primary_claim_id"] in finding.get("claim_ids", [])
            for finding in review["findings"]
        ):
            raise ValueError(f"{expected_lens} primary finding mismatch")
    return review


def reconcile_available_deliveries(
    usability_delivery: object,
    integrity_delivery: object,
) -> dict[str, object]:
    usability = _review_from_available_delivery(usability_delivery, "decision_usability")
    integrity = _review_from_available_delivery(integrity_delivery, "source_integrity")
    return reconcile(usability, integrity)


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input is not a regular non-symlink file: {path}")
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_pairs_no_duplicates,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {token}")
        ),
    )


def reconcile(usability: object, integrity: object) -> dict[str, object]:
    usability_errors = validate_review(usability, "decision_usability")
    integrity_errors = validate_review(integrity, "source_integrity")
    errors = usability_errors + integrity_errors
    if errors:
        raise ValueError("; ".join(errors))
    assert isinstance(usability, dict)
    assert isinstance(integrity, dict)
    if usability["case_id"] != integrity["case_id"]:
        raise ValueError("case_id mismatch")
    if integrity["material_failure"] is True or integrity["disposition"] == "BLOCK":
        verdict = "BLOCK"
        veto_source = "source_integrity"
    elif usability["material_failure"] is True or usability["disposition"] == "BLOCK":
        verdict = "BLOCK"
        veto_source = "decision_usability"
    elif "REVISE" in {usability["disposition"], integrity["disposition"]}:
        verdict = "REVISE"
        veto_source = "none"
    else:
        verdict = "READY_FOR_HUMAN_REVIEW"
        veto_source = "none"
    accepted_findings = [
        {
            "lens": review["lens"],
            "finding_id": finding["finding_id"],
            "severity": finding["severity"],
            "claim_ids": finding["claim_ids"],
        }
        for review in (usability, integrity)
        for finding in review["findings"]
    ]
    return {
        "case_id": usability["case_id"],
        "verdict": verdict,
        "veto_source": veto_source,
        "accepted_findings": accepted_findings,
        "reviewer_digests": {
            "decision_usability": _digest(usability),
            "source_integrity": _digest(integrity),
        },
        "residual_risk": {
            "decision_usability": usability["residual_risk"],
            "source_integrity": integrity["residual_risk"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--usability-delivery", required=True, type=Path)
    parser.add_argument("--integrity-delivery", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        usability_delivery = _read_json(args.usability_delivery)
        integrity_delivery = _read_json(args.integrity_delivery)
        result = reconcile_available_deliveries(usability_delivery, integrity_delivery)
        if args.output.is_symlink():
            raise ValueError("output must not be a symlink")
        with args.output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"reconciliation failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
