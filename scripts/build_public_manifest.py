"""Build a deterministic manifest for the public Skills Lab candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Iterator


SCHEMA_VERSION = "agent-skills-lab-public-manifest/v1"
REVISION = "private-remote-publication-2026-08-31"
RESIDUE_NAMES = {".DS_Store", "." + "git", "__py" + "cache__"}
RESIDUE_SUFFIXES = {".pyc", ".pyo"}
LIVE_COVERAGE_IGNORED_DIRECTORIES = {"." + "git", "__py" + "cache__"}
LIVE_COVERAGE_IGNORED_FILE_NAMES = {".DS_Store"}
LIVE_COVERAGE_IGNORED_FILE_SUFFIXES = {".pyc"}


class ManifestError(ValueError):
    """Raised when the candidate tree cannot be safely manifested."""


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _relative(root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ManifestError("output must stay inside candidate root") from error
    if not relative.parts or any(part in {".", ".."} for part in relative.parts):
        raise ManifestError("unsafe relative path")
    return relative.as_posix()


def _walk_regular_files(root: Path) -> Iterator[Path]:
    try:
        entries = sorted(os.scandir(root), key=lambda entry: entry.name)
    except OSError as error:
        raise ManifestError("candidate directory is unreadable") from error

    for entry in entries:
        path = root / entry.name
        if entry.name in RESIDUE_NAMES or path.suffix.casefold() in RESIDUE_SUFFIXES:
            raise ManifestError(f"generated residue is not public: {entry.name}")
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
        except OSError as error:
            raise ManifestError(f"candidate path is unreadable: {entry.name}") from error
        if stat.S_ISLNK(mode):
            raise ManifestError(f"symlink is not public: {entry.name}")
        if stat.S_ISDIR(mode):
            yield from _walk_regular_files(path)
        elif stat.S_ISREG(mode):
            yield path
        else:
            raise ManifestError(f"unsafe path type: {entry.name}")


def _walk_live_coverage_files(root: Path) -> Iterator[Path]:
    try:
        entries = sorted(os.scandir(root), key=lambda entry: entry.name)
    except OSError as error:
        raise ManifestError("live tree directory is unreadable") from error

    for entry in entries:
        path = root / entry.name
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
        except OSError as error:
            raise ManifestError(f"live tree path is unreadable: {entry.name}") from error
        if stat.S_ISLNK(mode):
            raise ManifestError(f"live tree symlink is unsafe: {entry.name}")
        if stat.S_ISDIR(mode):
            if entry.name not in LIVE_COVERAGE_IGNORED_DIRECTORIES:
                yield from _walk_live_coverage_files(path)
        elif stat.S_ISREG(mode):
            if (
                entry.name not in LIVE_COVERAGE_IGNORED_FILE_NAMES
                and path.suffix not in LIVE_COVERAGE_IGNORED_FILE_SUFFIXES
            ):
                yield path
        else:
            raise ManifestError(f"unsafe live tree path type: {entry.name}")


def live_tree_coverage_paths(root: Path) -> list[str]:
    """Return every non-residue regular file that Git publication must account for."""

    root = _absolute(root)
    try:
        root_mode = root.lstat().st_mode
    except OSError as error:
        raise ManifestError("live tree root is unreadable") from error
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise ManifestError("live tree root must be a real directory")
    return sorted(_relative(root, path) for path in _walk_live_coverage_files(root))


def manifest_for(root: Path, output: Path) -> dict[str, object]:
    """Return the exact manifest for *root* without writing it."""

    root = _absolute(root)
    output = _absolute(output)
    output_relative = _relative(root, output)
    try:
        root_mode = root.lstat().st_mode
    except OSError as error:
        raise ManifestError("candidate root is unreadable") from error
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise ManifestError("candidate root must be a real directory")
    if output.exists() and output.is_symlink():
        raise ManifestError("manifest output cannot be a symlink")

    entries: list[dict[str, object]] = []
    for path in _walk_regular_files(root):
        relative = _relative(root, path)
        if relative == output_relative:
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise ManifestError(f"candidate file is unreadable: {relative}") from error
        entries.append(
            {
                "path": relative,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    entries.sort(key=lambda entry: str(entry["path"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": REVISION,
        "self_entry": "excluded_by_design",
        "entries": entries,
    }


def build_manifest(root: Path, output: Path) -> dict[str, object]:
    """Validate *root*, then atomically write its manifest to *output*."""

    root = _absolute(root)
    output = _absolute(output)
    manifest = manifest_for(root, output)
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ManifestError("manifest parent must be a real existing directory")
    encoded = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".manifest-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except OSError as error:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise ManifestError("manifest write failed") from error
    return manifest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args(argv)
    try:
        manifest = build_manifest(Path(arguments.root), Path(arguments.output))
    except ManifestError as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({"entries": len(manifest["entries"]), "status": "ok"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
