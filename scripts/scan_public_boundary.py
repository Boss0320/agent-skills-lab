"""Default-deny scanner for a locally assembled public candidate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata
from typing import Any, Iterator


REQUIRED_POLICY_KEYS = {
    "allowed_binary_suffixes",
    "forbidden_path_fragments",
    "forbidden_suffixes",
    "minimum_phrase_tokens",
    "private_source_roots",
    "secret_patterns",
}
TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
SUFFIX_PATTERN = re.compile(r"\.[A-Za-z0-9]+\Z")
TEXT_WHITESPACE = {"\t", "\n", "\r"}
APPROVED_ROOT_GITIGNORE_PATH = "." + "gitignore"
APPROVED_ROOT_GITIGNORE_TEXT = "__py" + "cache__/\n*.pyc\n.DS_Store\n"


def _finding(code: str, path: str, evidence: str, severity: str = "ERROR") -> dict[str, str]:
    return {"code": code, "path": path, "evidence": evidence, "severity": severity}


def _sort_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(findings, key=lambda item: (item["path"], item["code"], item["evidence"]))


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _safe_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not any(unicodedata.category(char) in {"Cc", "Cf"} for char in value)
    )


def _valid_string_list(value: object, *, allow_empty: bool) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(_safe_string(item) for item in value)


def _valid_absolute_path(value: str) -> bool:
    try:
        path = Path(value)
    except (TypeError, ValueError):
        return False
    return path.is_absolute() and "." not in path.parts and ".." not in path.parts


def _validate_policy(policy: object) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(policy, dict) or set(policy) != REQUIRED_POLICY_KEYS:
        return None, "exact-policy-keys-required"
    list_keys = {
        "private_source_roots": True,
        "allowed_binary_suffixes": True,
        "forbidden_suffixes": False,
        "forbidden_path_fragments": False,
        "secret_patterns": False,
    }
    if any(not _valid_string_list(policy[key], allow_empty=allow_empty) for key, allow_empty in list_keys.items()):
        return None, "invalid-string-list"
    if any(not _valid_absolute_path(path) for path in policy["private_source_roots"]):
        return None, "unsafe-private-source-path"
    for key in ("forbidden_suffixes", "allowed_binary_suffixes"):
        if any(SUFFIX_PATTERN.fullmatch(suffix) is None for suffix in policy[key]):
            return None, "invalid-suffix"
    if not isinstance(policy["minimum_phrase_tokens"], int) or isinstance(policy["minimum_phrase_tokens"], bool):
        return None, "invalid-minimum-phrase-tokens"
    if policy["minimum_phrase_tokens"] < 1:
        return None, "invalid-minimum-phrase-tokens"
    try:
        for pattern in policy["secret_patterns"]:
            if len(pattern) > 512 or re.compile(pattern).search("") is not None:
                return None, "unsafe-secret-pattern"
    except re.error:
        return None, "unsafe-secret-pattern"
    return policy, None


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(_normalized(text))


def _shingles(text: str, minimum_tokens: int) -> set[str]:
    tokens = _tokens(text)
    return {"\x1f".join(tokens[index : index + minimum_tokens]) for index in range(len(tokens) - minimum_tokens + 1)}


def _read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        data = path.read_bytes()
    except (OSError, ValueError):
        return None, "path-unreadable"
    if b"\x00" in data:
        return None, "binary-content"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "binary-content"
    if any(ord(char) < 32 and char not in TEXT_WHITESPACE for char in text):
        return None, "binary-content"
    return text, None


def _walk(root: Path) -> Iterator[tuple[Path, int | None, str | None]]:
    try:
        entries = sorted(os.scandir(root), key=lambda entry: entry.name)
    except (OSError, ValueError):
        yield root, None, "directory-unreadable"
        return
    for entry in entries:
        path = root / entry.name
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
        except (OSError, ValueError):
            yield path, None, "lstat-failed"
            continue
        yield path, mode, None
        if stat.S_ISDIR(mode):
            yield from _walk(path)


def _private_identifier(index: int, source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return f"private-root:{index}:sha256:{digest}"


def _private_invalid(findings: list[dict[str, str]], identifier: str, category: str) -> None:
    findings.append(_finding("PRIVATE_SOURCE_INVALID", identifier, f"category:{category}"))


def _private_shingles(source_roots: list[str], minimum_tokens: int) -> tuple[set[str], list[dict[str, str]]]:
    shingles: set[str] = set()
    findings: list[dict[str, str]] = []
    ordered_roots = sorted(source_roots, key=_normalized)
    for index, raw_source in enumerate(ordered_roots):
        identifier = _private_identifier(index, raw_source)
        try:
            source = Path(raw_source)
            source_mode = source.lstat().st_mode
        except (OSError, ValueError):
            _private_invalid(findings, identifier, "root-unreadable")
            continue
        if stat.S_ISLNK(source_mode) or not (stat.S_ISREG(source_mode) or stat.S_ISDIR(source_mode)):
            _private_invalid(findings, identifier, "unsafe-root")
            continue
        entries = [(source, source_mode, None)] if stat.S_ISREG(source_mode) else _walk(source)
        for path, mode, error in entries:
            if error:
                _private_invalid(findings, identifier, error)
                continue
            assert mode is not None
            if stat.S_ISDIR(mode):
                continue
            if stat.S_ISLNK(mode):
                _private_invalid(findings, identifier, "symlink-rejected")
                continue
            if not stat.S_ISREG(mode):
                _private_invalid(findings, identifier, "unsafe-path-type")
                continue
            text, error = _read_text(path)
            if error:
                _private_invalid(findings, identifier, error)
                continue
            assert text is not None
            shingles.update(_shingles(text, minimum_tokens))
    return shingles, findings


def _relative_path(root: Path, path: Path) -> str | None:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return None


def _binary_allowed(path: Path, allowed_suffixes: set[str]) -> bool:
    return _normalized(path.suffix) in allowed_suffixes


def scan_tree(root: Path, policy: dict) -> list[dict]:
    """Return deterministic, default-deny findings for *root* under *policy*."""
    checked_policy, policy_error = _validate_policy(policy)
    if policy_error:
        return [_finding("POLICY_INVALID", "<policy>", policy_error, "CRITICAL")]
    assert checked_policy is not None
    try:
        root_path = Path(root).absolute()
        root_mode = root_path.lstat().st_mode
    except (OSError, TypeError, ValueError):
        return [_finding("ROOT_INVALID", "<root>", "root-unreadable", "CRITICAL")]
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        return [_finding("ROOT_INVALID", "<root>", "root-must-be-real-directory", "CRITICAL")]

    private_shingles, findings = _private_shingles(
        checked_policy["private_source_roots"], checked_policy["minimum_phrase_tokens"]
    )
    secret_patterns = [re.compile(pattern) for pattern in checked_policy["secret_patterns"]]
    fragments = [(_normalized(fragment), fragment) for fragment in checked_policy["forbidden_path_fragments"]]
    forbidden_suffixes = [(_normalized(suffix), suffix) for suffix in checked_policy["forbidden_suffixes"]]
    allowed_suffixes = {_normalized(suffix) for suffix in checked_policy["allowed_binary_suffixes"]}

    for path, mode, error in _walk(root_path):
        relative_path = _relative_path(root_path, path)
        if relative_path is None:
            findings.append(_finding("PATH_OUTSIDE_ROOT", "<outside>", "path-containment-failed", "CRITICAL"))
            continue
        if error:
            findings.append(_finding("TRAVERSAL_ERROR", relative_path, error))
            continue
        assert mode is not None
        normalized_path = _normalized(f"/{relative_path}")
        is_root_gitignore_file = (
            relative_path == APPROVED_ROOT_GITIGNORE_PATH and stat.S_ISREG(mode)
        )
        if not is_root_gitignore_file:
            for fragment, evidence in fragments:
                if fragment in normalized_path:
                    findings.append(
                        _finding("FORBIDDEN_PATH_FRAGMENT", relative_path, f"fragment:{evidence}")
                    )
        if stat.S_ISDIR(mode):
            continue
        if stat.S_ISLNK(mode):
            findings.append(_finding("SYMLINK", relative_path, "symlink-rejected"))
            continue
        if not stat.S_ISREG(mode):
            findings.append(_finding("UNSAFE_PATH_TYPE", relative_path, "non-regular-path"))
            continue
        normalized_name = _normalized(path.name)
        for suffix, evidence in forbidden_suffixes:
            if normalized_name.endswith(suffix):
                findings.append(_finding("FORBIDDEN_SUFFIX", relative_path, f"suffix:{evidence}"))
        text, error = _read_text(path)
        if error:
            if error == "binary-content" and _binary_allowed(path, allowed_suffixes):
                continue
            findings.append(_finding("BINARY_CONTENT", relative_path, "content-not-safe-to-scan"))
            continue
        assert text is not None
        normalized_text = _normalized(text)
        approved_root_gitignore = (
            is_root_gitignore_file and text == APPROVED_ROOT_GITIGNORE_TEXT
        )
        if not approved_root_gitignore:
            if is_root_gitignore_file:
                for fragment, evidence in fragments:
                    if fragment in normalized_path:
                        findings.append(
                            _finding("FORBIDDEN_PATH_FRAGMENT", relative_path, f"fragment:{evidence}")
                        )
            for fragment, evidence in fragments:
                if fragment in normalized_text:
                    findings.append(
                        _finding("FORBIDDEN_PATH_FRAGMENT", relative_path, f"fragment:{evidence}")
                    )
        for pattern in secret_patterns:
            if pattern.search(text):
                findings.append(_finding("SECRET_PATTERN", relative_path, f"pattern:{pattern.pattern}"))
        for shingle in sorted(_shingles(text, checked_policy["minimum_phrase_tokens"]) & private_shingles):
            digest = hashlib.sha256(shingle.encode("utf-8")).hexdigest()
            findings.append(_finding("PRIVATE_PHRASE_OVERLAP", relative_path, f"sha256:{digest}"))
    return _sort_findings(findings)


def _parse_cli_arguments(arguments: list[str]) -> tuple[str, str] | None:
    if len(arguments) != 4:
        return None
    parsed: dict[str, str] = {}
    for index in range(0, len(arguments), 2):
        flag = arguments[index]
        value = arguments[index + 1]
        if flag not in {"--root", "--policy"} or flag in parsed or not value or value.startswith("-"):
            return None
        parsed[flag] = value
    if set(parsed) != {"--root", "--policy"}:
        return None
    return parsed["--root"], parsed["--policy"]


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parsed_arguments = _parse_cli_arguments(arguments)
    if parsed_arguments is None:
        findings = [_finding("CLI_USAGE", "<cli>", "required-named-flags-root-and-policy", "CRITICAL")]
    else:
        root, raw_policy_path = parsed_arguments
        try:
            policy_path = Path(raw_policy_path).absolute()
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            findings = [_finding("POLICY_INVALID", "<policy>", "policy-file-unreadable", "CRITICAL")]
        else:
            findings = scan_tree(Path(root), policy)
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
