from __future__ import annotations

import hashlib
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
from typing import Any
import unicodedata


class AssemblyError(ValueError):
    """Raised when a public-candidate assembly input is unsafe or inconsistent."""


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_ENTRY_KEYS = frozenset({"path", "size", "sha256"})
_APPROVED_GITIGNORE = "." + "gitignore"
_APPROVED_EXTENSIONLESS = frozenset({_APPROVED_GITIGNORE})
_SYSTEM_ANCESTOR_SYMLINK_TARGETS = {
    Path("/tmp"): Path("/private/tmp"),
    Path("/var"): Path("/private/var"),
    Path("/etc"): Path("/private/etc"),
}


def validate_relative_path(value: str) -> Path:
    """Return a canonical safe relative manifest path, or raise AssemblyError."""
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise AssemblyError(f"unsafe manifest path: {value!r}")

    path = Path(value)
    windows_path = PureWindowsPath(value)
    approved_extensionless = value in _APPROVED_EXTENSIONLESS
    if (
        path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or path == Path(".")
        or str(path) != value
        or (any(part.startswith(".") for part in path.parts) and not approved_extensionless)
        or (path.name.casefold().endswith(_APPROVED_GITIGNORE) and not approved_extensionless)
    ):
        raise AssemblyError(f"unsafe manifest path: {value}")
    return path


def _canonical_manifest_key(path: Path) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in path.parts)


def _validate_root_ancestors(path: Path, label: str) -> None:
    """Reject symlink ancestors except fixed macOS system aliases.

    The three allowed aliases preserve normal /tmp and /var temporary-directory use
    on macOS. Every caller-controlled ancestor remains rejected; this favors a
    portable, conservative public-candidate boundary over filesystem inference.
    """
    current = path.absolute()
    try:
        while True:
            if current.is_symlink():
                expected_target = _SYSTEM_ANCESTOR_SYMLINK_TARGETS.get(current)
                if expected_target is None or current.resolve(strict=True) != expected_target:
                    raise AssemblyError(f"{label} root has symlink ancestor: {current}")
            if current.parent == current:
                return
            current = current.parent
    except OSError as error:
        raise AssemblyError(f"cannot inspect {label} root ancestors: {error}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries(entries: list[dict[str, Any]]) -> list[tuple[Path, int, str]]:
    if not isinstance(entries, list):
        raise AssemblyError("manifest entries must be a list")

    parsed: list[tuple[Path, int, str]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise AssemblyError("malformed manifest entry")

        relative_path = validate_relative_path(entry["path"])
        size = entry["size"]
        digest = entry["sha256"]
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or _DIGEST_PATTERN.fullmatch(digest) is None
        ):
            raise AssemblyError(f"malformed manifest entry: {relative_path}")
        canonical_key = _canonical_manifest_key(relative_path)
        if canonical_key in seen_keys:
            raise AssemblyError(f"ambiguous manifest path: {relative_path.as_posix()}")

        seen_keys.add(canonical_key)
        parsed.append((relative_path, size, digest))
    return parsed


def _source_files(source_root: Path) -> dict[str, Path]:
    if source_root.is_symlink() or not source_root.is_dir():
        raise AssemblyError("source root must be a non-symlink directory")

    files: dict[str, Path] = {}

    def raise_walk_error(error: OSError) -> None:
        raise error

    try:
        for directory, directory_names, file_names in os.walk(
            source_root,
            followlinks=False,
            onerror=raise_walk_error,
        ):
            current = Path(directory)
            for name in sorted([*directory_names, *file_names]):
                candidate = current / name
                relative = candidate.relative_to(source_root).as_posix()
                if candidate.is_symlink():
                    raise AssemblyError(f"source contains symlink: {relative}")
                if candidate.is_dir():
                    continue
                if not candidate.is_file():
                    raise AssemblyError(f"source contains non-regular file: {relative}")
                files[relative] = candidate
    except OSError as error:
        raise AssemblyError(f"cannot inspect source root: {error}") from error
    return files


def _verify_source_path(source_root: Path, relative_path: Path) -> Path:
    candidate = source_root
    for part in relative_path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise AssemblyError(f"source contains symlink: {relative_path.as_posix()}")
    if not candidate.is_file():
        raise AssemblyError(f"manifest path is not a regular file: {relative_path.as_posix()}")
    return candidate


def _verify_digest_bound_file(source_root: Path, relative_path: Path, size: int, digest: str) -> Path:
    source_path = _verify_source_path(source_root, relative_path)
    try:
        if source_path.stat().st_size != size:
            raise AssemblyError(f"size mismatch: {relative_path.as_posix()}")
        if _sha256(source_path) != digest:
            raise AssemblyError(f"sha256 mismatch: {relative_path.as_posix()}")
    except OSError as error:
        raise AssemblyError(f"cannot read source file: {relative_path.as_posix()}") from error
    return source_path


def _validate_destination(destination_root: Path) -> None:
    _validate_root_ancestors(destination_root, "destination")
    if destination_root.exists() or destination_root.is_symlink():
        raise AssemblyError(f"destination already exists: {destination_root}")
    parent = destination_root.parent
    if parent.is_symlink() or not parent.is_dir():
        raise AssemblyError("destination parent must be a non-symlink directory")


def assemble(
    source_root: Path,
    destination_root: Path,
    entries: list[dict[str, Any]],
    strict: bool = True,
) -> dict[str, int]:
    """Build a new candidate directory from an exact manifest of regular files."""
    if not isinstance(source_root, Path) or not isinstance(destination_root, Path):
        raise AssemblyError("source and destination roots must be Path instances")
    if not isinstance(strict, bool):
        raise AssemblyError("strict must be a bool")

    parsed_entries = _manifest_entries(entries)
    _validate_root_ancestors(source_root, "source")
    _validate_destination(destination_root)
    source_files = _source_files(source_root)
    manifest_paths = {relative_path.as_posix() for relative_path, _, _ in parsed_entries}
    if strict:
        unlisted = sorted(set(source_files) - manifest_paths)
        if unlisted:
            raise AssemblyError(f"unlisted source file: {unlisted[0]}")

    verified_entries = [
        (_verify_digest_bound_file(source_root, relative_path, size, digest), relative_path, size, digest)
        for relative_path, size, digest in parsed_entries
    ]

    destination_root.mkdir()
    try:
        for source_path, relative_path, size, digest in verified_entries:
            _verify_digest_bound_file(source_root, relative_path, size, digest)
            destination_path = destination_root / relative_path
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination_path)
            if destination_path.stat().st_size != size or _sha256(destination_path) != digest:
                raise AssemblyError(f"copied file does not match manifest: {relative_path.as_posix()}")
    except (AssemblyError, OSError) as error:
        shutil.rmtree(destination_root)
        if isinstance(error, AssemblyError):
            raise
        raise AssemblyError(f"cannot assemble candidate: {error}") from error

    return {"copied_files": len(verified_entries)}
