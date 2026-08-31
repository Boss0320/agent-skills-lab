from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "agent-system-integration-audit"
SCRIPT = SKILL_ROOT / "scripts" / "validate_detection_record.py"


def load_module():
    if not SCRIPT.is_file():
        raise AssertionError(f"missing module: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("detection_record_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(status: str = "BOUNDARY_MISMATCH_OBSERVED") -> dict[str, object]:
    return {
        "scope": "SYNTHETIC-DATAFLOW-SLICE",
        "observed_status": status,
        "producer": {
            "path": "src/producer.py",
            "symbol": "build_signal",
            "observed_behavior": "Produces decision_basis with every signal.",
        },
        "consumer": {
            "path": "src/consumer.py",
            "symbol": "render_signal",
            "observed_behavior": "Receives no decision_basis after adaptation.",
        },
        "boundary_contract": "decision_basis must survive producer-to-consumer adaptation.",
        "evidence": [
            {
                "path": "src/producer.py",
                "line": 8,
                "excerpt": 'return {"signal": signal, "decision_basis": basis}',
                "role": "producer",
            },
            {
                "path": "src/consumer.py",
                "line": 12,
                "excerpt": 'return payload["decision_basis"]',
                "role": "consumer",
            },
        ],
        "contradicting_paths_checked": [
            {
                "path": "src/adapter.py",
                "observation": "The adapter rebuilds the payload without decision_basis.",
            }
        ],
        "bypass_paths_checked": [
            {
                "path": "src/composition.py",
                "observation": "The required consumer is reached only through this adapter.",
            }
        ],
        "verification": {
            "command": "python3 -m unittest tests.test_required_path -v",
            "observed_output": "FAIL: decision_basis missing at consumer",
            "reach": "Exercises producer -> adapter -> required consumer in one process.",
        },
        "unobserved_paths": ["Optional batch entrypoint was not executed."],
        "residual_risk": "Only the declared synchronous required path was executed.",
    }


def materialize_root(root: Path, value: dict[str, object]) -> None:
    paths = {
        value["producer"]["path"],
        value["consumer"]["path"],
        *(item["path"] for item in value["contradicting_paths_checked"]),
        *(item["path"] for item in value["bypass_paths_checked"]),
        *(item["path"] for item in value["evidence"]),
    }
    for relative in paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(["placeholder"] * 20) + "\n", encoding="utf-8")
    by_path: dict[str, list[dict[str, object]]] = {}
    for item in value["evidence"]:
        by_path.setdefault(item["path"], []).append(item)
    for relative, items in by_path.items():
        path = root / relative
        lines = path.read_text(encoding="utf-8").splitlines()
        for item in items:
            lines[item["line"] - 1] = item["excerpt"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class DetectionRecordValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_valid_material_and_clean_records_are_answer_neutral(self) -> None:
        self.assertEqual([], self.module.validate_record(record()))
        clean = record("BOUNDARY_MATCH_OBSERVED")
        clean["consumer"]["observed_behavior"] = "Receives the declared decision_basis."
        clean["contradicting_paths_checked"][0]["observation"] = "The adapter preserves decision_basis."
        clean["verification"]["observed_output"] = "OK: required consumer received decision_basis"
        self.assertEqual([], self.module.validate_record(clean))
        serialized = json.dumps(clean).casefold()
        for forbidden in ("expected_dimension", "grader_label", "hidden_answer"):
            self.assertNotIn(forbidden, serialized)
        for status in self.module.STATUSES:
            for taxonomy in ("MATERIAL", "CRITICAL", "MINOR", "DIMENSION"):
                self.assertNotIn(taxonomy, status)

    def test_rejects_extra_keys_and_answer_labels(self) -> None:
        mutated = record()
        mutated["expected_dimension"] = 3
        self.assertIn("record keys mismatch", self.module.validate_record(mutated))

    def test_rejects_unsafe_paths_bool_lines_and_duplicate_evidence(self) -> None:
        unsafe = record()
        unsafe["producer"]["path"] = "../producer.py"
        self.assertTrue(any("path invalid" in item for item in self.module.validate_record(unsafe)))

        boolean = record()
        boolean["evidence"][0]["line"] = True
        self.assertTrue(any("line invalid" in item for item in self.module.validate_record(boolean)))

        duplicate = record()
        duplicate["evidence"].append(deepcopy(duplicate["evidence"][0]))
        self.assertTrue(any("duplicate evidence identity" in item for item in self.module.validate_record(duplicate)))

    def test_rejects_control_characters_missing_reach_and_closure_language(self) -> None:
        controlled = record()
        controlled["boundary_contract"] = "unsafe\tcontract"
        self.assertTrue(any("boundary_contract" in item for item in self.module.validate_record(controlled)))

        no_reach = record()
        no_reach["verification"]["reach"] = ""
        self.assertTrue(any("reach invalid" in item for item in self.module.validate_record(no_reach)))

        overclaim = record("BOUNDARY_MATCH_OBSERVED")
        overclaim["residual_risk"] = "No residual risk; all paths tested and production ready."
        self.assertTrue(any("unsupported closure language" in item for item in self.module.validate_record(overclaim)))

    def test_impossible_relationships_fail_closed(self) -> None:
        no_consumer = record()
        no_consumer["evidence"] = [no_consumer["evidence"][0]]
        self.assertTrue(any("producer and consumer evidence" in item for item in self.module.validate_record(no_consumer)))

        no_path_search = record()
        no_path_search["bypass_paths_checked"] = []
        self.assertTrue(any("bypass_paths_checked" in item for item in self.module.validate_record(no_path_search)))

    def test_evidence_is_bound_to_regular_files_and_exact_source_lines(self) -> None:
        value = record()
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            materialize_root(root, value)
            self.assertEqual([], self.module.validate_evidence_bytes(value, root))

            wrong_excerpt = deepcopy(value)
            wrong_excerpt["evidence"][0]["excerpt"] = "not present in source"
            self.assertTrue(
                any("excerpt mismatch" in item for item in self.module.validate_evidence_bytes(wrong_excerpt, root))
            )

            missing_path = deepcopy(value)
            missing_path["bypass_paths_checked"][0]["path"] = "src/missing.py"
            self.assertTrue(
                any("regular file" in item for item in self.module.validate_evidence_bytes(missing_path, root))
            )

    def test_cli_rejects_duplicate_json_keys_without_stderr(self) -> None:
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            path = Path(temporary) / "detection-record.json"
            path.write_text('{"scope":"one","scope":"two"}', encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(path),
                    "--root",
                    str(root),
                    "--max-bytes",
                    "12000",
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        self.assertEqual(2, completed.returncode)
        self.assertEqual("", completed.stderr)
        self.assertFalse(json.loads(completed.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
