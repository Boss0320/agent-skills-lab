from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.assemble_pilot_executor_bundle import CASE_ALIASES
except ModuleNotFoundError:  # Direct script execution puts this directory first.
    from assemble_pilot_executor_bundle import CASE_ALIASES


ROOT = Path(__file__).resolve().parents[1]
AUDIT_VALIDATOR_PATH = (
    ROOT / "skills" / "agent-system-integration-audit" / "scripts" / "validate_audit_packet.py"
)


def _load_audit_validator():
    spec = importlib.util.spec_from_file_location("pilot_frozen_audit_validator", AUDIT_VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("frozen audit validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_pilot_packet(
    packet: object,
    catalog: object,
    internal_case_id: str,
    executor_case_id: str,
) -> list[str]:
    """Validate a packet against frozen truth while preserving opaque scope."""
    if not isinstance(internal_case_id, str) or not isinstance(executor_case_id, str):
        return ["case IDs must be strings"]
    if CASE_ALIASES.get(internal_case_id) != executor_case_id:
        return ["executor case ID is not bound to the selected internal case"]

    audit = _load_audit_validator()
    catalog_errors, cases = audit.validate_catalog(catalog)
    if catalog_errors:
        return catalog_errors
    selected = cases.get(internal_case_id)
    if selected is None:
        return [f"case not found: {internal_case_id}"]

    aliased_case: dict[str, Any] = copy.deepcopy(selected)
    aliased_case["case_id"] = executor_case_id
    aliased_case["project_root"] = f"fixtures/cases/{executor_case_id}"
    return audit.validate_packet(packet, aliased_case)


def _parse_arguments(arguments: list[str]) -> dict[str, str] | None:
    required = {"--packet", "--catalog", "--case", "--executor-case"}
    if len(arguments) != 8:
        return None
    values: dict[str, str] = {}
    for index in range(0, len(arguments), 2):
        flag, value = arguments[index], arguments[index + 1]
        if flag not in required or flag in values or not value or value.startswith("-"):
            return None
        values[flag] = value
    return values if set(values) == required else None


def main(arguments: list[str] | None = None) -> int:
    values = _parse_arguments(list(sys.argv[1:] if arguments is None else arguments))
    if values is None:
        print(
            json.dumps(
                {"errors": ["usage requires --packet PATH --catalog PATH --case CASE_ID --executor-case OPAQUE_ID"]},
                separators=(",", ":"),
            )
        )
        return 2

    audit = _load_audit_validator()
    packet, packet_error = audit._read_json(values["--packet"], "packet")
    catalog, catalog_error = audit._read_json(values["--catalog"], "catalog")
    errors = [error for error in (packet_error, catalog_error) if error is not None]
    if not errors:
        errors.extend(
            validate_pilot_packet(
                packet,
                catalog,
                values["--case"],
                values["--executor-case"],
            )
        )
    if errors:
        print(json.dumps({"errors": errors}, separators=(",", ":"), sort_keys=True))
        return 2
    print(json.dumps({"status": "valid"}, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
