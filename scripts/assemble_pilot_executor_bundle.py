from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any
import unicodedata

try:
    from scripts.assemble_public_candidate import AssemblyError, assemble
except ModuleNotFoundError:  # Direct script execution puts this directory first.
    from assemble_public_candidate import AssemblyError, assemble


class PilotBundleError(ValueError):
    """Raised when an executor bundle cannot be assembled safely."""


CASE_PROJECTS = {
    "D03-DATAFLOW": "CedarSignals",
    "D02-SCHEMA": "NorthstarMetrics",
    "D08-ADAPTER": "HarborWeather",
    "D12-SEMANTIC": "MeridianLimits",
    "D11-REQUIRED-PATH": "CobaltDispatch",
    "CLEAN-01": "JuniperTickets",
    "CLEAN-02": "WillowLimits",
    "CLEAN-03": "SableFallback",
}
CASE_ALIASES = {
    "D03-DATAFLOW": "CASE-CEDAR",
    "D02-SCHEMA": "CASE-EMBER",
    "D08-ADAPTER": "CASE-HARBOR",
    "D12-SEMANTIC": "CASE-MERIDIAN",
    "D11-REQUIRED-PATH": "CASE-COBALT",
    "CLEAN-01": "CASE-JUNIPER",
    "CLEAN-02": "CASE-WILLOW",
    "CLEAN-03": "CASE-SABLE",
}
CASE_FILE_PATHS = (
    "src/contracts.py",
    "src/component.py",
    "src/integration.py",
    "config/system.json",
    "tests/test_system.py",
)
MANIFEST_KEYS = {"case_id", "project_name", "file_sha256"}
SKILL_FILE_PATHS = (
    "SKILL.md",
    "references/audit-contract.md",
    "references/detection-workflow.md",
    "scripts/validate_detection_record.py",
)
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PilotBundleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise PilotBundleError(f"invalid JSON constant: {value}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_entry(path: Path, relative: str, digest: str | None = None) -> dict[str, object]:
    return {
        "path": relative,
        "size": path.stat().st_size,
        "sha256": _sha256(path) if digest is None else digest,
    }


def _read_case_manifest(case_root: Path, case_id: str) -> tuple[Path, dict[str, str]]:
    manifest_path = case_root / "case-manifest.json"
    try:
        raw = manifest_path.read_bytes()
        if len(raw) > 64 * 1024:
            raise PilotBundleError("case manifest is too large")
        manifest = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        if isinstance(error, PilotBundleError):
            raise
        raise PilotBundleError(f"case manifest unreadable: {error}") from error
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise PilotBundleError("case manifest keys must be exact and answer-free")
    if manifest["case_id"] != case_id or manifest["project_name"] != CASE_PROJECTS[case_id]:
        raise PilotBundleError("case manifest identity mismatch")
    digest_map = manifest["file_sha256"]
    if not isinstance(digest_map, dict) or set(digest_map) != set(CASE_FILE_PATHS):
        raise PilotBundleError("case manifest file list must be exact")
    if any(not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None for digest in digest_map.values()):
        raise PilotBundleError("case manifest digests must be lowercase SHA-256")
    return manifest_path, digest_map


def _project_entries(case_root: Path, case_id: str) -> tuple[list[dict[str, object]], dict[str, str]]:
    _, digest_map = _read_case_manifest(case_root, case_id)
    entries = [_manifest_entry(case_root / relative, relative, digest_map[relative]) for relative in CASE_FILE_PATHS]
    return entries, digest_map


def _skill_entries(skill_root: Path) -> list[dict[str, object]]:
    return [_manifest_entry(skill_root / relative, relative) for relative in SKILL_FILE_PATHS]


def assemble_pilot_bundle(
    candidate_root: Path,
    case_id: str,
    destination_root: Path,
) -> dict[str, int | str]:
    """Create one answer-free project bundle and its minimal Skill companion."""
    if not isinstance(candidate_root, Path) or not isinstance(destination_root, Path):
        raise PilotBundleError("candidate and destination roots must be Path instances")
    if case_id not in CASE_PROJECTS:
        raise PilotBundleError(f"unknown pilot case: {case_id}")
    executor_case_id = CASE_ALIASES[case_id]
    if destination_root.name != executor_case_id:
        raise PilotBundleError("destination basename must equal the opaque executor case ID")
    if destination_root.exists() or destination_root.is_symlink():
        raise PilotBundleError("destination must be new")
    if destination_root.parent.is_symlink() or not destination_root.parent.is_dir():
        raise PilotBundleError("destination parent must be a non-symlink directory")

    skill_root = candidate_root / "skills" / "agent-system-integration-audit"
    case_root = skill_root / "fixtures" / "cases" / case_id
    try:
        project_entries, digest_map = _project_entries(case_root, case_id)
        skill_entries = _skill_entries(skill_root)
        destination_root.mkdir()
        project_result = assemble(case_root, destination_root / "project", project_entries, strict=False)
        sanitized_manifest = {
            "case_id": executor_case_id,
            "project_name": CASE_PROJECTS[case_id],
            "file_sha256": digest_map,
        }
        (destination_root / "project" / "case-manifest.json").write_text(
            json.dumps(sanitized_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        skill_result = assemble(skill_root, destination_root / "skill", skill_entries, strict=False)
    except (AssemblyError, OSError, PilotBundleError, TypeError, ValueError) as error:
        if destination_root.exists() and destination_root.is_dir() and not destination_root.is_symlink():
            shutil.rmtree(destination_root)
        if isinstance(error, PilotBundleError):
            raise
        raise PilotBundleError(str(error)) from error

    return {
        "case_id": case_id,
        "executor_case_id": executor_case_id,
        "project_files": project_result["copied_files"] + 1,
        "skill_files": skill_result["copied_files"],
    }


def _parse_arguments(arguments: list[str]) -> tuple[str, Path] | None:
    if len(arguments) != 4:
        return None
    values: dict[str, str] = {}
    for index in range(0, len(arguments), 2):
        flag, value = arguments[index], arguments[index + 1]
        if flag not in {"--case", "--destination"} or flag in values or not value or value.startswith("-"):
            return None
        values[flag] = value
    if set(values) != {"--case", "--destination"} or values["--case"] not in CASE_PROJECTS:
        return None
    raw_destination = values["--destination"]
    destination = Path(raw_destination)
    if (
        not destination.is_absolute()
        or raw_destination != str(destination)
        or raw_destination != unicodedata.normalize("NFC", raw_destination)
        or any(unicodedata.category(character) in {"Cc", "Cf"} for character in raw_destination)
        or "\x00" in raw_destination
        or "\\" in raw_destination
        or "//" in raw_destination
        or raw_destination.endswith("/")
        or any(part in {".", ".."} for part in destination.parts)
    ):
        return None
    return values["--case"], destination


def main(arguments: list[str] | None = None) -> int:
    parsed = _parse_arguments(list(sys.argv[1:] if arguments is None else arguments))
    if parsed is None:
        print(json.dumps({"errors": ["usage requires --case CASE_ID --destination ABSOLUTE_NEW_PATH"]}, separators=(",", ":")))
        return 2
    case_id, destination = parsed
    try:
        result = assemble_pilot_bundle(Path(__file__).resolve().parents[1], case_id, destination)
    except PilotBundleError as error:
        print(json.dumps({"errors": [str(error)]}, separators=(",", ":")))
        return 2
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
