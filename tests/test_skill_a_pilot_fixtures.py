from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "agent-system-integration-audit"
CASES_ROOT = SKILL_ROOT / "fixtures" / "cases"
CATALOG_PATH = SKILL_ROOT / "fixtures" / "catalog.json"
CASE_FILES = {
    "case-manifest.json",
    "src/contracts.py",
    "src/component.py",
    "src/integration.py",
    "config/system.json",
    "tests/test_system.py",
}
IMPLEMENTED_CASES = {
    "D02-SCHEMA": {
        "project_name": "NorthstarMetrics",
        "finding": {
            "finding_id": "D02-F01",
            "severity": "MATERIAL",
            "dimension": 2,
            "evidence": "src/contracts.py:21",
        },
    },
    "D08-ADAPTER": {
        "project_name": "HarborWeather",
        "finding": {
            "finding_id": "D08-F01",
            "severity": "MATERIAL",
            "dimension": 8,
            "evidence": "src/component.py:81",
        },
    },
    "D12-SEMANTIC": {
        "project_name": "MeridianLimits",
        "finding": {
            "finding_id": "D12-F01",
            "severity": "CRITICAL",
            "dimension": 12,
            "evidence": "src/contracts.py:121",
        },
    },
    "CLEAN-01": {"project_name": "JuniperTickets", "finding": None},
    "CLEAN-02": {"project_name": "WillowLimits", "finding": None},
}
EXPECTED_EVALS = {
    "skill_name": "agent-system-integration-audit",
    "evals": [
        {
            "id": 1,
            "prompt": "Audit HarborWeather after its recent integration refactor. Return every required audit deliverable. Do not edit it.",
            "expected_output": "Detect the material defect, classify it as D08-F01, cite the bound evidence, and preserve bytes.",
            "files": ["fixtures/cases/D08-ADAPTER"],
            "expectations": [
                "Detects the material defect",
                "Assigns expected taxonomy",
                "Produces a validator-valid packet",
                "Does not modify bytes",
            ],
        },
        {
            "id": 2,
            "prompt": "Audit MeridianLimits after its recent integration refactor. Return every required audit deliverable. Do not edit it.",
            "expected_output": "Detect the cross-boundary material defect, classify it as D12-F01, cite the bound evidence, and preserve bytes.",
            "files": ["fixtures/cases/D12-SEMANTIC"],
            "expectations": [
                "Detects the material defect",
                "Assigns expected taxonomy",
                "Produces a validator-valid packet",
                "Does not modify bytes",
            ],
        },
        {
            "id": 3,
            "prompt": "Audit JuniperTickets after its recent integration refactor. Return every required audit deliverable. Do not edit it.",
            "expected_output": "Return no material finding, produce a validator-valid packet, and preserve bytes.",
            "files": ["fixtures/cases/CLEAN-01"],
            "expectations": [
                "Returns zero material findings",
                "Produces a validator-valid packet",
                "Does not modify bytes",
            ],
        },
        {
            "id": 4,
            "prompt": "Audit WillowLimits after its recent integration refactor. Return every required audit deliverable. Do not edit it.",
            "expected_output": "Return no material finding for the semantic near-miss, produce a validator-valid packet, and preserve bytes.",
            "files": ["fixtures/cases/CLEAN-02"],
            "expectations": [
                "Returns zero material findings",
                "Produces a validator-valid packet",
                "Does not modify bytes",
            ],
        },
    ],
}
EXPECTED_DESCRIPTION = (
    "Audit multi-module agent systems after cross-file changes, new tools, adapter updates, configuration changes, "
    "prompt changes, event wiring, or authority-flow changes. Use this Skill whenever the user asks for an "
    "integration audit, end-to-end wiring review, semantic contract check, or evidence-backed release review, "
    "even when unit tests are already green."
)
CACHE_DIR = "_" * 2 + "pycache" + "_" * 2


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _json(path: Path) -> object:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )


def _relative_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ast_nodes_on_line(path: Path, line: int) -> list[ast.AST]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node
        for node in ast.walk(tree)
        if getattr(node, "lineno", None) == line and isinstance(node, (ast.AnnAssign, ast.Return))
    ]


def _refresh_manifest_digest(case_root: Path, relative: str) -> None:
    manifest_path = case_root / "case-manifest.json"
    manifest = _json(manifest_path)
    assert isinstance(manifest, dict)
    digest_map = manifest["file_sha256"]
    assert isinstance(digest_map, dict)
    digest_map[relative] = _sha256(case_root / relative)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


class PilotFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        catalog = _json(CATALOG_PATH)
        assert isinstance(catalog, dict)
        cls.catalog_by_id = {case["case_id"]: case for case in catalog["cases"]}

    def test_exact_case_inventory_has_no_hidden_cache_or_symlink_residue(self) -> None:
        for case_id in IMPLEMENTED_CASES:
            case_root = CASES_ROOT / case_id
            self.assertTrue(case_root.is_dir(), case_id)
            self.assertFalse(case_root.is_symlink(), case_id)
            self.assertEqual(_relative_files(case_root), CASE_FILES, case_id)
            for path in case_root.rglob("*"):
                relative = path.relative_to(case_root)
                self.assertFalse(path.is_symlink(), relative.as_posix())
                self.assertFalse(any(part.startswith(".") for part in relative.parts), relative.as_posix())
                self.assertFalse(any(part == CACHE_DIR for part in relative.parts), relative.as_posix())

    def test_manifests_are_closed_catalog_bound_and_digest_exact(self) -> None:
        hex_digest = re.compile(r"[0-9a-f]{64}")
        for case_id, expected in IMPLEMENTED_CASES.items():
            case_root = CASES_ROOT / case_id
            manifest = _json(case_root / "case-manifest.json")
            self.assertIsInstance(manifest, dict)
            self.assertEqual(set(manifest), {"case_id", "project_name", "file_sha256"})
            self.assertEqual(manifest["case_id"], case_id)
            self.assertEqual(manifest["project_name"], expected["project_name"])

            digest_map = manifest["file_sha256"]
            self.assertIsInstance(digest_map, dict)
            self.assertEqual(set(digest_map), CASE_FILES - {"case-manifest.json"})
            for relative, digest in digest_map.items():
                self.assertRegex(digest, hex_digest)
                self.assertEqual(digest, _sha256(case_root / relative), f"{case_id}:{relative}")

            catalog_case = self.catalog_by_id[case_id]
            self.assertEqual(catalog_case["project_root"], f"fixtures/cases/{case_id}")
            self.assertEqual(catalog_case["clean_control"], expected["finding"] is None)
            self.assertEqual(
                catalog_case["dimension"],
                None if expected["finding"] is None else expected["finding"]["dimension"],
            )
            self.assertEqual(
                catalog_case["severity"],
                None if expected["finding"] is None else expected["finding"]["severity"],
            )
            self.assertEqual(
                catalog_case["expected_finding_ids"],
                [] if expected["finding"] is None else [expected["finding"]["finding_id"]],
            )
            self.assertEqual(
                catalog_case["expected_evidence"],
                {} if expected["finding"] is None else {
                    expected["finding"]["finding_id"]: expected["finding"]["evidence"]
                },
            )

    def test_python_and_json_files_parse(self) -> None:
        for case_id in IMPLEMENTED_CASES:
            case_root = CASES_ROOT / case_id
            for relative in CASE_FILES:
                path = case_root / relative
                if path.suffix == ".py":
                    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                elif path.suffix == ".json":
                    _json(path)

    def _assert_d02_defect_is_on_the_active_boundary(self, case_root: Path) -> None:
        path = case_root / "src" / "contracts.py"
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertIn('Literal["quarterly"]', "\n".join(lines[:20]))
        self.assertEqual(lines[20].strip(), 'period: Literal["year_to_date"]')
        self.assertTrue(_ast_nodes_on_line(path, 21), "evidence line must contain parsed schema code")

        integration_path = case_root / "src" / "integration.py"
        tree = ast.parse(integration_path.read_text(encoding="utf-8"), filename=str(integration_path))
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        summarize = functions["summarize"]
        self.assertIsInstance(summarize.args.args[0].annotation, ast.Name)
        self.assertEqual(summarize.args.args[0].annotation.id, "ConsumerReport")
        run_pipeline = functions["run_pipeline"]
        assignments = [node for node in run_pipeline.body if isinstance(node, ast.Assign)]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(ast.unparse(assignments[0]), "produced = build_report()")
        returns = [node for node in run_pipeline.body if isinstance(node, ast.Return)]
        self.assertEqual(len(returns), 1)
        self.assertEqual(ast.unparse(returns[0].value), "summarize(produced)")

        probe = """
from typing import get_args, get_type_hints

from src.component import build_report
from src.contracts import ConsumerReport
from src.integration import run_pipeline

produced = build_report()
assert produced["period"] == "quarterly"
assert get_args(get_type_hints(ConsumerReport)["period"]) == ("year_to_date",)
assert run_pipeline() == "north:quarterly:42.0"
"""
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=case_root,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_d02_defect_is_active_and_repair_or_disconnect_mutation_fails(self) -> None:
        case_root = CASES_ROOT / "D02-SCHEMA"
        self._assert_d02_defect_is_on_the_active_boundary(case_root)
        with tempfile.TemporaryDirectory() as temporary:
            repaired = Path(temporary) / "repaired"
            shutil.copytree(case_root, repaired)
            contracts_path = repaired / "src" / "contracts.py"
            contracts_path.write_text(
                contracts_path.read_text(encoding="utf-8").replace(
                    'period: Literal["year_to_date"]', 'period: Literal["quarterly"]'
                ),
                encoding="utf-8",
            )
            _refresh_manifest_digest(repaired, "src/contracts.py")
            self.assertEqual(
                _json(repaired / "case-manifest.json")["file_sha256"]["src/contracts.py"],
                _sha256(contracts_path),
            )
            with self.assertRaises(AssertionError):
                self._assert_d02_defect_is_on_the_active_boundary(repaired)

            disconnected = Path(temporary) / "disconnected"
            shutil.copytree(case_root, disconnected)
            integration_path = disconnected / "src" / "integration.py"
            integration_path.write_text(
                integration_path.read_text(encoding="utf-8").replace(
                    "return summarize(produced)", 'return "disconnected"'
                ),
                encoding="utf-8",
            )
            _refresh_manifest_digest(disconnected, "src/integration.py")
            self.assertEqual(
                _json(disconnected / "case-manifest.json")["file_sha256"]["src/integration.py"],
                _sha256(integration_path),
            )
            with self.assertRaises(AssertionError):
                self._assert_d02_defect_is_on_the_active_boundary(disconnected)

    def _assert_d08_defect_is_on_the_active_boundary(self, case_root: Path) -> None:
        contracts = (case_root / "src" / "contracts.py").read_text(encoding="utf-8")
        self.assertIn("observed_at", contracts)
        path = case_root / "src" / "component.py"
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertIn("return", lines[80])
        self.assertNotIn("observed_at", lines[80])
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        mock_class = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MockWeatherAdapter"
        )
        fetch = next(
            node for node in mock_class.body if isinstance(node, ast.FunctionDef) and node.name == "fetch"
        )
        returns = [node for node in ast.walk(fetch) if isinstance(node, ast.Return)]
        self.assertEqual([node.lineno for node in returns], [81])
        self.assertTrue(_ast_nodes_on_line(path, 81), "evidence line must contain parsed adapter code")

        probe = """
from src.component import MockWeatherAdapter
from src.contracts import WeatherObservation
from src.integration import render_station

observation = MockWeatherAdapter().fetch("HBR-1")
assert set(observation) == {"station", "temperature_c"}
assert set(WeatherObservation.__required_keys__) == {"station", "temperature_c", "observed_at"}
assert "observed_at" not in observation
try:
    render_station("mock")
except KeyError as error:
    assert error.args == ("observed_at",)
else:
    raise AssertionError("mock rendering unexpectedly succeeded")
"""
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=case_root,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_d08_defect_is_active_and_repair_mutation_fails(self) -> None:
        case_root = CASES_ROOT / "D08-ADAPTER"
        self._assert_d08_defect_is_on_the_active_boundary(case_root)
        with tempfile.TemporaryDirectory() as temporary:
            repaired = Path(temporary) / "repaired"
            shutil.copytree(case_root, repaired)
            component_path = repaired / "src" / "component.py"
            lines = component_path.read_text(encoding="utf-8").splitlines()
            lines[80] = '        return _base_observation(station) | {"temperature_c": 19.5}'
            component_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            _refresh_manifest_digest(repaired, "src/component.py")
            self.assertEqual(
                _json(repaired / "case-manifest.json")["file_sha256"]["src/component.py"],
                _sha256(component_path),
            )
            with self.assertRaises(AssertionError):
                self._assert_d08_defect_is_on_the_active_boundary(repaired)

    def _assert_d12_semantic_defect_is_on_the_active_boundary(self, case_root: Path) -> None:
        contracts_path = case_root / "src" / "contracts.py"
        lines = contracts_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[120].strip(), 'threshold_basis: Literal["percent"]')
        self.assertTrue(_ast_nodes_on_line(contracts_path, 121), "evidence line must contain parsed contract code")

        probe = """
import json
from pathlib import Path

from src.component import normalized_observation
from src.integration import evaluate_account, load_rule

observation = normalized_observation("ACCT-7")
rule = load_rule(json.loads(Path("config/system.json").read_text(encoding="utf-8")))
assert observation == {"account_id": "ACCT-7", "drawdown": 0.075, "drawdown_basis": "ratio"}
assert rule == {"threshold": 5.0, "threshold_basis": "percent"}
assert observation["drawdown"] < rule["threshold"]
assert observation["drawdown"] >= rule["threshold"] / 100
assert evaluate_account("ACCT-7") == "ALLOW"
"""
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=case_root,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_d12_semantic_defect_is_active_and_repair_mutation_fails(self) -> None:
        case_root = CASES_ROOT / "D12-SEMANTIC"
        self._assert_d12_semantic_defect_is_on_the_active_boundary(case_root)
        with tempfile.TemporaryDirectory() as temporary:
            repaired = Path(temporary) / "repaired"
            shutil.copytree(case_root, repaired)
            integration_path = repaired / "src" / "integration.py"
            integration_path.write_text(
                integration_path.read_text(encoding="utf-8").replace(
                    'threshold = rule["threshold"]',
                    'threshold = rule["threshold"] / 100',
                ),
                encoding="utf-8",
            )
            _refresh_manifest_digest(repaired, "src/integration.py")
            with self.assertRaises(AssertionError):
                self._assert_d12_semantic_defect_is_on_the_active_boundary(repaired)

    def test_clean_control_contract_adapters_config_and_delegation_align(self) -> None:
        case_root = CASES_ROOT / "CLEAN-01"
        probe = """
import json
from pathlib import Path

from src.component import MockTicketAdapter, ProductionTicketAdapter
from src.integration import TicketCoordinator, build_coordinator

expected = {"ticket_id", "status", "owner"}
for adapter in (ProductionTicketAdapter(), MockTicketAdapter()):
    assert set(adapter.fetch("JT-100")) == expected
    assert TicketCoordinator(adapter).summarize("JT-100")["ticket_id"] == "JT-100"
config = json.loads(Path("config/system.json").read_text(encoding="utf-8"))
expected = set(config["required_fields"])
assert set(build_coordinator(config).summarize("JT-100")) == expected
class IncompleteAdapter:
    def fetch(self, ticket_id):
        return {"ticket_id": ticket_id, "status": "open"}
class ExtraFieldAdapter:
    def fetch(self, ticket_id):
        return {"ticket_id": ticket_id, "status": "open", "owner": "cedar", "debug": "on"}
try:
    TicketCoordinator(IncompleteAdapter()).summarize("JT-100")
except ValueError:
    pass
else:
    raise AssertionError("incomplete adapter record accepted")
try:
    TicketCoordinator(ExtraFieldAdapter()).summarize("JT-100")
except ValueError:
    pass
else:
    raise AssertionError("extra-field adapter record accepted")
try:
    TicketCoordinator(IncompleteAdapter(), ("ticket_id", "status"))
except TypeError:
    pass
else:
    raise AssertionError("weakened constructor accepted")
for invalid in (
    config | {"coordinator": "unknown"},
    config | {"required_fields": ["missing_field"]},
    config | {"extra": "not_closed"},
):
    try:
        build_coordinator(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"invalid config accepted: {invalid}")
"""
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=case_root,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            _json(case_root / "config" / "system.json"),
            {"adapter": "production", "coordinator": "ticket_summary", "required_fields": ["ticket_id", "status", "owner"]},
        )

    def _assert_clean_02_converts_the_threshold_before_comparison(self, case_root: Path) -> None:
        probe = """
import json
from pathlib import Path

from src.component import normalized_observation
from src.integration import evaluate_account, load_rule

observation = normalized_observation("ACCT-7")
rule = load_rule(json.loads(Path("config/system.json").read_text(encoding="utf-8")))
assert observation == {"account_id": "ACCT-7", "drawdown": 0.075, "drawdown_basis": "ratio"}
assert rule == {"threshold": 5.0, "threshold_basis": "percent"}
assert evaluate_account("ACCT-7") == "BLOCK"
"""
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=case_root,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clean_02_semantic_near_miss_and_broken_conversion_mutation(self) -> None:
        case_root = CASES_ROOT / "CLEAN-02"
        self._assert_clean_02_converts_the_threshold_before_comparison(case_root)
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "broken"
            shutil.copytree(case_root, broken)
            integration_path = broken / "src" / "integration.py"
            integration_path.write_text(
                integration_path.read_text(encoding="utf-8").replace(
                    'threshold_ratio = rule["threshold"] / 100',
                    'threshold_ratio = rule["threshold"]',
                ),
                encoding="utf-8",
            )
            _refresh_manifest_digest(broken, "src/integration.py")
            with self.assertRaises(AssertionError):
                self._assert_clean_02_converts_the_threshold_before_comparison(broken)

    def test_each_fixture_isolated_system_test_is_green(self) -> None:
        for case_id in IMPLEMENTED_CASES:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "tests/test_system.py", "-v"],
                cwd=CASES_ROOT / case_id,
                env={"PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{case_id}\nstdout={result.stdout}\nstderr={result.stderr}")

    def test_eval_set_is_the_exact_harder_iteration_two_pilot(self) -> None:
        self.assertEqual(_json(SKILL_ROOT / "evals" / "evals.json"), EXPECTED_EVALS)

    def test_skill_frontmatter_and_read_only_deliverables_are_closed(self) -> None:
        path = SKILL_ROOT / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertLess(len(lines), 500)
        self.assertGreaterEqual(len(lines), 5)
        self.assertEqual(lines[0], "---")
        self.assertEqual(lines[1], "name: agent-system-integration-audit")
        self.assertEqual(lines[2], f"description: {EXPECTED_DESCRIPTION}")
        self.assertEqual(lines[3], "---")
        required_phrases = (
            "read-only",
            "references/audit-contract.md",
            "audit-packet.json",
            "audit-report.md",
            "local green tests do not prove integration",
            "scope",
            "case_id",
            "unverified Accept",
            "root closure",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, text)
        for forbidden_direction in (
            "fixtures/catalog.json",
            "validate_audit_packet.py",
            "expected_output",
            "expected finding",
        ):
            self.assertNotIn(forbidden_direction, text)


if __name__ == "__main__":
    unittest.main()
