from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import unicodedata


RECORD_KEYS = {
    "scope",
    "observed_status",
    "producer",
    "consumer",
    "boundary_contract",
    "evidence",
    "contradicting_paths_checked",
    "bypass_paths_checked",
    "verification",
    "unobserved_paths",
    "residual_risk",
}
NODE_KEYS = {"path", "symbol", "observed_behavior"}
EVIDENCE_KEYS = {"path", "line", "excerpt", "role"}
PATH_CHECK_KEYS = {"path", "observation"}
VERIFICATION_KEYS = {"command", "observed_output", "reach"}
STATUSES = {
    "BOUNDARY_MISMATCH_OBSERVED",
    "BOUNDARY_MATCH_OBSERVED",
    "INSUFFICIENT_EVIDENCE",
}
ROLES = {"contract", "producer", "transform", "consumer", "bypass", "probe"}
UNSUPPORTED_CLOSURE = {
    "all paths tested",
    "fully verified",
    "no residual risk",
    "production ready",
    "root closed",
    "universal coverage",
}


def _safe_string(value: object, *, allow_lf: bool = False) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    for character in value:
        if allow_lf and character == "\n":
            continue
        if unicodedata.category(character) in {"Cc", "Cf"}:
            return False
    return True


def _safe_path(value: object) -> bool:
    if not _safe_string(value) or not isinstance(value, str) or "\\" in value:
        return False
    parts = value.split("/")
    return (
        not value.startswith("/")
        and all(part not in {"", ".", ".."} for part in parts)
        and not Path(value).is_absolute()
    )


def _validate_node(value: object, label: str) -> list[str]:
    if not isinstance(value, dict) or set(value) != NODE_KEYS:
        return [f"{label} keys mismatch"]
    errors: list[str] = []
    if not _safe_path(value["path"]):
        errors.append(f"{label}.path invalid")
    for key in ("symbol", "observed_behavior"):
        if not _safe_string(value[key]):
            errors.append(f"{label}.{key} invalid")
    return errors


def _validate_evidence(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["evidence must be a non-empty array"]
    errors: list[str] = []
    identities: set[tuple[str, int]] = set()
    roles: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"evidence[{index}]"
        if not isinstance(item, dict) or set(item) != EVIDENCE_KEYS:
            errors.append(f"{prefix} keys mismatch")
            continue
        if not _safe_path(item["path"]):
            errors.append(f"{prefix}.path invalid")
        line = item["line"]
        if isinstance(line, bool) or not isinstance(line, int) or line <= 0:
            errors.append(f"{prefix}.line invalid")
            continue
        if not _safe_string(item["excerpt"]):
            errors.append(f"{prefix}.excerpt invalid")
        if item["role"] not in ROLES:
            errors.append(f"{prefix}.role invalid")
        else:
            roles.add(item["role"])
        identity = (unicodedata.normalize("NFC", str(item["path"])).casefold(), line)
        if identity in identities:
            errors.append(f"{prefix} duplicate evidence identity")
        identities.add(identity)
    if not {"producer", "consumer"}.issubset(roles):
        errors.append("producer and consumer evidence are both required")
    return errors


def _validate_path_checks(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{label} must be a non-empty array"]
    errors: list[str] = []
    identities: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"{label}[{index}]"
        if not isinstance(item, dict) or set(item) != PATH_CHECK_KEYS:
            errors.append(f"{prefix} keys mismatch")
            continue
        if not _safe_path(item["path"]):
            errors.append(f"{prefix}.path invalid")
        if not _safe_string(item["observation"]):
            errors.append(f"{prefix}.observation invalid")
        identity = unicodedata.normalize("NFC", str(item["path"])).casefold()
        if identity in identities:
            errors.append(f"{prefix} duplicate path")
        identities.add(identity)
    return errors


def _validate_verification(value: object) -> list[str]:
    if not isinstance(value, dict) or set(value) != VERIFICATION_KEYS:
        return ["verification keys mismatch"]
    errors: list[str] = []
    if not _safe_string(value["command"]):
        errors.append("verification.command invalid")
    if not _safe_string(value["observed_output"], allow_lf=True):
        errors.append("verification.observed_output invalid")
    if not _safe_string(value["reach"]):
        errors.append("verification.reach invalid")
    return errors


def validate_record(record: object) -> list[str]:
    if not isinstance(record, dict) or set(record) != RECORD_KEYS:
        return ["record keys mismatch"]
    errors: list[str] = []
    if not _safe_string(record["scope"]):
        errors.append("scope invalid")
    if record["observed_status"] not in STATUSES:
        errors.append("observed_status invalid")
    errors.extend(_validate_node(record["producer"], "producer"))
    errors.extend(_validate_node(record["consumer"], "consumer"))
    if not _safe_string(record["boundary_contract"]):
        errors.append("boundary_contract invalid")
    errors.extend(_validate_evidence(record["evidence"]))
    errors.extend(_validate_path_checks(record["contradicting_paths_checked"], "contradicting_paths_checked"))
    errors.extend(_validate_path_checks(record["bypass_paths_checked"], "bypass_paths_checked"))
    errors.extend(_validate_verification(record["verification"]))
    unobserved = record["unobserved_paths"]
    if (
        not isinstance(unobserved, list)
        or any(not _safe_string(item) for item in unobserved)
        or len(unobserved) != len(set(unobserved))
    ):
        errors.append("unobserved_paths invalid")
    if not _safe_string(record["residual_risk"]):
        errors.append("residual_risk invalid")
    closure_text = " ".join(
        [str(record["residual_risk"]), str(record["verification"].get("reach", ""))]
        if isinstance(record["verification"], dict)
        else [str(record["residual_risk"])]
    ).casefold()
    if any(phrase in closure_text for phrase in UNSUPPORTED_CLOSURE):
        errors.append("unsupported closure language")
    if isinstance(record["evidence"], list):
        evidence_paths = {
            (item.get("role"), item.get("path"))
            for item in record["evidence"]
            if isinstance(item, dict)
        }
        for role in ("producer", "consumer"):
            node = record[role]
            if isinstance(node, dict) and (role, node.get("path")) not in evidence_paths:
                errors.append(f"{role} node lacks matching evidence")
    return errors


def _bound_file(root: Path, relative: str, label: str) -> tuple[Path | None, str | None]:
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink():
            return None, f"{label} must reference a regular non-symlink file"
    try:
        if not current.is_file() or not current.resolve().is_relative_to(root.resolve()):
            return None, f"{label} must reference a regular file inside root"
    except OSError as error:
        return None, f"{label} file check failed: {error}"
    return current, None


def validate_evidence_bytes(record: object, root: Path) -> list[str]:
    structural = validate_record(record)
    if structural:
        return structural
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        return ["root must be a regular non-symlink directory"]
    assert isinstance(record, dict)
    errors: list[str] = []
    referenced: list[tuple[str, str]] = []
    for label in ("producer", "consumer"):
        referenced.append((f"{label}.path", record[label]["path"]))
    for field in ("contradicting_paths_checked", "bypass_paths_checked"):
        for index, item in enumerate(record[field]):
            referenced.append((f"{field}[{index}].path", item["path"]))
    for label, relative in referenced:
        _, error = _bound_file(root, relative, label)
        if error is not None:
            errors.append(error)
    for index, item in enumerate(record["evidence"]):
        label = f"evidence[{index}]"
        path, error = _bound_file(root, item["path"], f"{label}.path")
        if error is not None:
            errors.append(error)
            continue
        assert path is not None
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as read_error:
            errors.append(f"{label}.path unreadable: {read_error}")
            continue
        line = item["line"]
        if line > len(lines):
            errors.append(f"{label}.line exceeds source length")
        elif item["excerpt"] not in lines[line - 1]:
            errors.append(f"{label}.excerpt mismatch at declared source line")
    return errors


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, max_bytes: int) -> tuple[object, bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("input must be a regular non-symlink file")
    payload = path.read_bytes()
    if len(payload) > max_bytes:
        raise ValueError(f"input exceeds {max_bytes} bytes")
    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_pairs_no_duplicates,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {token}")
        ),
    )
    return value, payload


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _emit(result: dict[str, object]) -> None:
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--max-bytes", type=int, default=12000)
    try:
        args = parser.parse_args(argv)
        if args.max_bytes <= 0:
            raise ValueError("max-bytes must be positive")
        record, payload = _load(args.input, args.max_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        _emit({"valid": False, "errors": [{"code": "INPUT_INVALID", "message": str(error)}]})
        return 2
    errors = validate_record(record)
    if not errors:
        errors = validate_evidence_bytes(record, args.root)
    if errors:
        _emit({"valid": False, "errors": [{"code": "RECORD_INVALID", "message": item} for item in errors]})
        return 1
    _emit({"valid": True, "errors": [], "sha256": hashlib.sha256(payload).hexdigest()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
