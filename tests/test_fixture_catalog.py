"""Completeness checks for Task 6's public synthetic fixture identities."""

from __future__ import annotations

import json
from pathlib import Path
import copy
import unittest

from tests.test_audit_packet_validator import load_validator


CATALOG = (
    Path(__file__).resolve().parents[1]
    / "skills/agent-system-integration-audit/fixtures/catalog.json"
)

EXPECTED_CASE_IDS = {
    "D01-DEPENDENCY",
    "D02-SCHEMA",
    "D03-DATAFLOW",
    "D04-AUTHORITY",
    "D05-CONFIG",
    "D06-FALLBACK",
    "D07-IMPORT",
    "D08-ADAPTER",
    "D09-EVENT",
    "D10-PROMPT-TOOL",
    "D11-REQUIRED-PATH",
    "D12-SEMANTIC",
    "CLEAN-01",
    "CLEAN-02",
    "CLEAN-03",
    "MIXED-CRITICAL-01",
    "MIXED-MATERIAL-01",
}
FROZEN_CASE_SPECS = {
    "D01-DEPENDENCY": (1, "MATERIAL", ("D01-F01",), ("src/contracts.py:11",)),
    "D02-SCHEMA": (2, "MATERIAL", ("D02-F01",), ("src/contracts.py:21",)),
    "D03-DATAFLOW": (3, "MATERIAL", ("D03-F01",), ("src/integration.py:8",)),
    "D04-AUTHORITY": (4, "CRITICAL", ("D04-F01",), ("src/component.py:41",)),
    "D05-CONFIG": (5, "MATERIAL", ("D05-F01",), ("src/contracts.py:51",)),
    "D06-FALLBACK": (6, "MATERIAL", ("D06-F01",), ("src/component.py:61",)),
    "D07-IMPORT": (7, "MINOR", ("D07-F01",), ("src/contracts.py:71",)),
    "D08-ADAPTER": (8, "MATERIAL", ("D08-F01",), ("src/component.py:81",)),
    "D09-EVENT": (9, "MATERIAL", ("D09-F01",), ("src/integration.py:91",)),
    "D10-PROMPT-TOOL": (10, "CRITICAL", ("D10-F01",), ("src/integration.py:101",)),
    "D11-REQUIRED-PATH": (11, "MATERIAL", ("D11-F01",), ("src/integration.py:15",)),
    "D12-SEMANTIC": (12, "CRITICAL", ("D12-F01",), ("src/contracts.py:121",)),
    "MIXED-CRITICAL-01": (4, "CRITICAL", ("MIXED-C-F01", "MIXED-C-F02"), ("src/component.py:141", "src/integration.py:142")),
    "MIXED-MATERIAL-01": (8, "MATERIAL", ("MIXED-M-F01", "MIXED-M-F02"), ("src/contracts.py:151", "src/component.py:152")),
}
ALLOWED_EVIDENCE_PATHS = {"src/contracts.py", "src/component.py", "src/integration.py"}
CASE_KEYS = {
    "case_id",
    "dimension",
    "severity",
    "expected_finding_ids",
    "clean_control",
    "project_root",
    "expected_evidence",
}


class FixtureCatalogTests(unittest.TestCase):
    def test_catalog_has_the_complete_safe_identity_set(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual({"cases"}, set(catalog))
        cases = catalog["cases"]
        self.assertEqual(17, len(cases))
        self.assertEqual(EXPECTED_CASE_IDS, {case["case_id"] for case in cases})
        self.assertEqual(17, len({case["case_id"] for case in cases}))
        self.assertTrue(all(set(case) == CASE_KEYS for case in cases))

        dimension_cases = [case for case in cases if case["case_id"].startswith("D")]
        self.assertEqual(set(range(1, 13)), {case["dimension"] for case in dimension_cases})
        self.assertEqual(3, sum(case["clean_control"] for case in cases))
        self.assertEqual(2, sum(case["case_id"].startswith("MIXED-") for case in cases))

        all_finding_ids = [
            finding_id for case in cases for finding_id in case["expected_finding_ids"]
        ]
        self.assertEqual(len(all_finding_ids), len(set(all_finding_ids)))
        for case in cases:
            self.assertTrue(case["project_root"].startswith("fixtures/cases/"))
            self.assertFalse(Path(case["project_root"]).is_absolute())
            self.assertNotIn("..", Path(case["project_root"]).parts)
            self.assertEqual(
                set(case["expected_finding_ids"]), set(case["expected_evidence"])
            )
            for identity in case["expected_evidence"].values():
                path, line = identity.rsplit(":", 1)
                self.assertFalse(Path(path).is_absolute())
                self.assertNotIn("..", Path(path).parts)
                self.assertTrue(path)
                self.assertGreater(int(line), 0)

    def test_clean_controls_have_no_seeded_dimension_or_severity(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        clean_cases = [case for case in catalog["cases"] if case["clean_control"]]
        self.assertTrue(
            all(
                case["dimension"] is None
                and case["severity"] is None
                and case["expected_finding_ids"] == []
                and case["expected_evidence"] == {}
                for case in clean_cases
            )
        )

    def test_catalog_matches_the_documented_future_realizable_frozen_mapping(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cases = {case["case_id"]: case for case in catalog["cases"]}
        for case_id, (dimension, severity, finding_ids, identities) in FROZEN_CASE_SPECS.items():
            case = cases[case_id]
            self.assertEqual(f"fixtures/cases/{case_id}", case["project_root"])
            self.assertEqual(dimension, case["dimension"])
            self.assertEqual(severity, case["severity"])
            self.assertEqual(list(finding_ids), case["expected_finding_ids"])
            self.assertEqual(
                list(identities),
                [case["expected_evidence"][finding_id] for finding_id in finding_ids],
            )
            self.assertTrue(
                all(identity.rsplit(":", 1)[0] in ALLOWED_EVIDENCE_PATHS for identity in identities)
            )
        for case_id in ("CLEAN-01", "CLEAN-02", "CLEAN-03"):
            case = cases[case_id]
            self.assertEqual(f"fixtures/cases/{case_id}", case["project_root"])
            self.assertIsNone(case["dimension"])
            self.assertIsNone(case["severity"])
            self.assertEqual([], case["expected_finding_ids"])
            self.assertEqual({}, case["expected_evidence"])

    def test_validator_rejects_any_mutation_of_the_frozen_catalog_identity(self) -> None:
        module = load_validator()
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual([], module.validate_catalog(catalog)[0])

        mutations = []
        removed = copy.deepcopy(catalog)
        removed["cases"].pop()
        mutations.append(removed)
        replaced = copy.deepcopy(catalog)
        replaced["cases"][0]["case_id"] = "REPLACED-CASE"
        mutations.append(replaced)
        duplicate_dimension = copy.deepcopy(catalog)
        duplicate_dimension["cases"][1]["dimension"] = 1
        mutations.append(duplicate_dimension)
        duplicate_finding = copy.deepcopy(catalog)
        duplicate_finding["cases"][1]["expected_finding_ids"] = ["D01-F01"]
        duplicate_finding["cases"][1]["expected_evidence"] = {"D01-F01": "src/record.py:21"}
        mutations.append(duplicate_finding)
        duplicate_root = copy.deepcopy(catalog)
        duplicate_root["cases"][1]["project_root"] = "fixtures/cases/d01-dependency"
        mutations.append(duplicate_root)
        empty_non_clean = copy.deepcopy(catalog)
        empty_non_clean["cases"][0]["expected_finding_ids"] = []
        empty_non_clean["cases"][0]["expected_evidence"] = {}
        mutations.append(empty_non_clean)
        invalid_identity = copy.deepcopy(catalog)
        invalid_identity["cases"][0]["project_root"] = "fixtures//cases/d01-dependency"
        mutations.append(invalid_identity)
        invalid_identity = copy.deepcopy(catalog)
        invalid_identity["cases"][0]["expected_evidence"] = {"D01-F01": "./src/composition.py:12"}
        mutations.append(invalid_identity)
        oversized_line = copy.deepcopy(catalog)
        oversized_line["cases"][0]["expected_evidence"] = {"D01-F01": f"src/composition.py:{'9' * 5000}"}
        mutations.append(oversized_line)

        for mutation in mutations:
            self.assertTrue(module.validate_catalog(mutation)[0])


if __name__ == "__main__":
    unittest.main()
