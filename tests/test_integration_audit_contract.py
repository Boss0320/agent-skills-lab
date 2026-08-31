"""Structural contract checks for the public integration-audit reference."""

import json
from pathlib import Path
import re
import unittest


CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "agent-system-integration-audit"
    / "references"
    / "audit-contract.md"
)
SKILL = CONTRACT.parents[1] / "SKILL.md"
DETECTION_REFERENCE = CONTRACT.with_name("detection-workflow.md")
EXPECTED_DIMENSIONS = {
    1: "Dependency construction", 2: "Schema", 3: "Dataflow", 4: "Authority",
    5: "Configuration", 6: "Fallback behavior", 7: "Imports and declared dependencies",
    8: "Adapter parity", 9: "Events", 10: "Instruction/prompt and callable-tool interface",
    11: "Required path", 12: "Semantic correctness",
}
EXPECTED_FINDING_KEYS = {
    "finding_id", "severity", "dimension", "secondary_dimensions", "claim",
    "expected_impact", "evidence", "verification_command", "observed_output",
    "root_closed_by", "residual_risk",
}
EXPECTED_RESULT_KEYS = {"status", "findings", "scope", "residual_risk"}


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def fenced_json_blocks(text: str) -> list[dict[str, object]]:
    blocks = re.findall(r"^```json\n(.*?)^```$", text, re.MULTILINE | re.DOTALL)
    return [json.loads(block, object_pairs_hook=reject_duplicate_keys) for block in blocks]


def validate_finding(finding: object) -> None:
    if not isinstance(finding, dict) or set(finding) != EXPECTED_FINDING_KEYS:
        raise AssertionError("finding keys must be exact")
    if finding["finding_id"] != "CASE-D04-F01":
        raise AssertionError("finding_id must be the synthetic authority fixture")
    if finding["severity"] not in {"CRITICAL", "MATERIAL", "MINOR"}:
        raise AssertionError("severity must use the public enum")
    if type(finding["dimension"]) is not int or not 1 <= finding["dimension"] <= 12:
        raise AssertionError("dimension must be an integer from 1 through 12")
    if not isinstance(finding["secondary_dimensions"], list) or any(
        type(value) is not int or not 1 <= value <= 12
        for value in finding["secondary_dimensions"]
    ):
        raise AssertionError("secondary dimensions must be dimension integers")
    for key in (
        "claim", "expected_impact", "verification_command", "observed_output",
        "root_closed_by", "residual_risk",
    ):
        if not isinstance(finding[key], str) or not finding[key].strip():
            raise AssertionError(f"{key} must be a non-empty string")
    if finding["root_closed_by"] == "Not closed by this audit.":
        raise AssertionError("root_closed_by must name concrete closure evidence")
    if not isinstance(finding["evidence"], list) or not finding["evidence"]:
        raise AssertionError("evidence must be a non-empty list")
    for item in finding["evidence"]:
        if not isinstance(item, dict) or set(item) != {"path", "line", "excerpt"}:
            raise AssertionError("evidence item keys must be exact")
        if not isinstance(item["path"], str) or not item["path"]:
            raise AssertionError("evidence path must be a non-empty string")
        if type(item["line"]) is not int or item["line"] < 1:
            raise AssertionError("evidence line must be a positive integer")
        if not isinstance(item["excerpt"], str) or not item["excerpt"]:
            raise AssertionError("evidence excerpt must be a non-empty string")


def validate_result(result: object, canonical: dict[str, object], status: str) -> None:
    if not isinstance(result, dict) or set(result) != EXPECTED_RESULT_KEYS:
        raise AssertionError("audit-result keys must be exact")
    if result["status"] != status:
        raise AssertionError("audit-result status must match its envelope")
    if not isinstance(result["findings"], list):
        raise AssertionError("audit-result findings must be a list")
    if status == "FINDINGS_REPORTED":
        if len(result["findings"]) != 1:
            raise AssertionError("FINDINGS_REPORTED requires non-empty findings")
        validate_finding(result["findings"][0])
        if result["findings"][0] != canonical:
            raise AssertionError("FINDINGS_REPORTED must contain the canonical finding")
    elif status == "CLEAN_CONTROL_PASS":
        if result["findings"] != []:
            raise AssertionError("CLEAN_CONTROL_PASS requires empty findings")
    else:
        raise AssertionError("unknown audit-result status")
    for key in ("scope", "residual_risk"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise AssertionError(f"result {key} must be a non-empty string")


def dimension_bodies(text: str) -> dict[int, tuple[str, str]]:
    headings = re.findall(r"^#{1,6} Dimension (\d+): (.+)$", text, re.MULTILINE)
    if [(int(number), title) for number, title in headings] != list(EXPECTED_DIMENSIONS.items()):
        raise AssertionError("dimension headings must be exactly 1 through 12")
    bodies: dict[int, tuple[str, str]] = {}
    pattern = re.compile(
        r"^#{1,6} Dimension (\d+): ([^\n]+)\n(.*?)(?=^#{1,6} |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for number, title, body in pattern.findall(text):
        bodies[int(number)] = (title, body.strip())
    if set(bodies) != set(EXPECTED_DIMENSIONS):
        raise AssertionError("each dimension must have a body")
    return bodies


def validate_contract(text: str) -> None:
    blocks = fenced_json_blocks(text)
    if len(blocks) != 3:
        raise AssertionError("contract must contain exactly three JSON blocks")
    canonical, reported, clean = blocks
    validate_finding(canonical)
    validate_result(reported, canonical, "FINDINGS_REPORTED")
    validate_result(clean, canonical, "CLEAN_CONTROL_PASS")
    if "`FINDINGS_REPORTED`" not in text or "`CLEAN_CONTROL_PASS`" not in text:
        raise AssertionError("both audit statuses must be declared")
    normalized_text = " ".join(text.split())

    forbidden = re.compile(
        r"(?i)\b(?:may|can|is authorized to|has authority to)"
        r"(?:\s+[a-z-]+){0,4}\s+(?:edit|repair|mutate|modify)\b"
    )
    if forbidden.search(text):
        raise AssertionError("affirmative edit or repair authority is forbidden")

    bodies = dimension_bodies(text)
    required_terms = {
        1: ("dependency", "construction"), 2: ("shape/type compatibility",),
        3: ("dataflow",), 4: ("authority",), 5: ("configuration",),
        6: ("fallback",), 7: ("imports", "declared dependencies"),
        8: ("adapter parity",), 9: ("events",),
        10: ("instruction/prompt alignment", "available/required callable-tool interface", "unavailable/omitted capability"),
        11: ("required path",),
        12: ("consumed parameters", "identity", "period", "unit", "basis", "freshness", "derivation", "stale documentation"),
    }
    for number, terms in required_terms.items():
        body = " ".join(bodies[number][1].lower().split())
        if any(term not in body for term in terms):
            raise AssertionError(f"dimension {number} lacks its required meaning")
    if "Dimension 2 covers shape/type compatibility; Dimension 12 covers correct use and meaning." not in text:
        raise AssertionError("Dimension 2/12 boundary must be explicit")
    if "This boundary makes finding attribution deterministic." not in text:
        raise AssertionError("Dimension 2/12 attribution must be deterministic")
    if "Later fixtures use one primary dimension and optional secondary dimensions." not in text:
        raise AssertionError("fixture dimension attribution must be explicit")
    if "Evidence must identify source actually inspected by the assessor." not in normalized_text:
        raise AssertionError("evidence must be answer neutral and inspection bound")
    if "A valid source location and sufficient observed behavior support the claim" not in normalized_text:
        raise AssertionError("evidence sufficiency rule must be explicit")
    if "catalog declares" in normalized_text or "declared primary identity" in normalized_text:
        raise AssertionError("contract must not depend on evaluator metadata")
    if "Additional unique supporting evidence is allowed." not in normalized_text:
        raise AssertionError("unique supporting evidence must be allowed")
    if "normalized LF (`\\n`) line breaks" not in normalized_text:
        raise AssertionError("observed output must declare normalized LF support")
    forbidden_controls_rule = (
        "Tabs, carriage returns, NUL, and all other Unicode `Cc` or `Cf` controls remain forbidden."
    )
    if forbidden_controls_rule not in normalized_text:
        raise AssertionError("observed output control boundary must stay explicit")
    if "Finding reported is not root closed." not in text:
        raise AssertionError("reporting and closure must remain distinct")
    if "An audit report is not a fix." not in text:
        raise AssertionError("audit must not be represented as a fix")
    if len(text.splitlines()) >= 500:
        raise AssertionError("contract must stay below 500 lines")


class IntegrationAuditContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = CONTRACT.read_text(encoding="utf-8")

    def test_contract_has_closed_typed_records_and_dimensions(self) -> None:
        validate_contract(self.text)

    def test_rejects_affirmative_repair_authority(self) -> None:
        with self.assertRaisesRegex(AssertionError, "affirmative edit"):
            validate_contract(self.text + "\nThe assessor may repair an observed route.\n")

    def test_rejects_fake_key_mention_and_removed_typed_key(self) -> None:
        mutated = self.text.replace('"expected_impact":', '"mentioned_expected_impact":', 1)
        with self.assertRaisesRegex(AssertionError, "finding keys must be exact"):
            validate_contract(mutated)

    def test_rejects_duplicate_json_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate JSON key: severity"):
            fenced_json_blocks('```json\n{"severity":"CRITICAL","severity":"MINOR"}\n```')

    def test_rejects_extra_dimension_heading(self) -> None:
        mutated = self.text + "\n#### Dimension 13: Extra\n\nExtra category.\n"
        with self.assertRaisesRegex(AssertionError, "exactly 1 through 12"):
            validate_contract(mutated)

    def test_rejects_dimension_twelve_semantic_erasure(self) -> None:
        start = self.text.index("### Dimension 12:")
        end = self.text.index("## Completion language", start)
        mutated = self.text[:start] + "### Dimension 12: Semantic correctness\n\nGeneric check.\n\n" + self.text[end:]
        with self.assertRaisesRegex(AssertionError, "dimension 12"):
            validate_contract(mutated)

    def test_rejects_empty_findings_reported_result(self) -> None:
        canonical, reported, _ = fenced_json_blocks(self.text)
        mutated = dict(reported, findings=[])
        with self.assertRaisesRegex(AssertionError, "FINDINGS_REPORTED requires non-empty"):
            validate_result(mutated, canonical, "FINDINGS_REPORTED")

    def test_rejects_untyped_finding_in_reported_result(self) -> None:
        canonical, reported, _ = fenced_json_blocks(self.text)
        mutated = dict(reported, findings=["not a typed finding"])
        with self.assertRaisesRegex(AssertionError, "finding keys must be exact"):
            validate_result(mutated, canonical, "FINDINGS_REPORTED")

    def test_skill_is_detection_first_before_taxonomy_and_packet_formatting(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        detection = DETECTION_REFERENCE.read_text(encoding="utf-8")
        required = [
            "detection-record.json",
            "validate_detection_record.py",
            "producer",
            "consumer",
            "contradicting",
            "bypass",
            "reach",
        ]
        for term in required:
            self.assertIn(term, skill + detection)
        self.assertLess(skill.index("detection-record.json"), skill.index("dimension"))
        self.assertIn("classify only after", (skill + detection).casefold())

    def test_public_detection_flow_has_no_catalog_or_grader_dependency(self) -> None:
        detection = DETECTION_REFERENCE.read_text(encoding="utf-8").casefold()
        validator = (CONTRACT.parents[1] / "scripts" / "validate_detection_record.py").read_text(encoding="utf-8").casefold()
        for forbidden in ("hidden catalog", "grader label", "expected dimension", "answer key"):
            self.assertNotIn(forbidden, detection + validator)


if __name__ == "__main__":
    unittest.main()
