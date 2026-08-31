from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.assemble_public_candidate import assemble
from scripts.scan_public_boundary import scan_tree


FRAGMENT_USERS = "/" + "Us" + "ers/"
FRAGMENT_GIT = "." + "g" + "it"
FRAGMENT_NODE = "node" + "_modules"
FRAGMENT_CACHE = "__py" + "cache__"
MIXED_NODE = "No" + "De_" + "MoDu" + "LeS"
GITIGNORE_NAME = FRAGMENT_GIT + "ignore"
APPROVED_GITIGNORE = FRAGMENT_CACHE + "/\n*.pyc\n.DS_Store\n"
POLICY = {
    "private_source_roots": [],
    "forbidden_suffixes": [".db"],
    "forbidden_path_fragments": [FRAGMENT_USERS, FRAGMENT_GIT, FRAGMENT_NODE, FRAGMENT_CACHE],
    "secret_patterns": [r"sk-[A-Za-z0-9]{8,}"],
    "minimum_phrase_tokens": 12,
    "allowed_binary_suffixes": [],
}
SCRIPT = Path(__file__).parents[1] / "scripts" / "scan_public_boundary.py"
LIVE_POLICY = Path(__file__).parents[2] / ".codex" / "skills-lab-private" / "boundary-policy.json"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "provenance" / "public-manifest.json"


class PublicBoundaryTests(unittest.TestCase):
    def test_allows_only_exact_approved_root_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            approved = root / GITIGNORE_NAME
            approved.write_text(APPROVED_GITIGNORE, encoding="utf-8")
            self.assertEqual(scan_tree(root, POLICY), [])

            approved.write_text(APPROVED_GITIGNORE + FRAGMENT_GIT + "/private\n", encoding="utf-8")
            self.assertIn("FORBIDDEN_PATH_FRAGMENT", {item["code"] for item in scan_tree(root, POLICY)})

        for relative_path in (
            f"{FRAGMENT_GIT}/config",
            f"nested/{FRAGMENT_GIT}/config",
            f"x{GITIGNORE_NAME}",
            f"nested/{GITIGNORE_NAME}",
        ):
            with self.subTest(relative_path=relative_path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(APPROVED_GITIGNORE, encoding="utf-8")
                self.assertIn(
                    "FORBIDDEN_PATH_FRAGMENT",
                    {item["code"] for item in scan_tree(root, POLICY)},
                )

    def test_flags_database_and_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "runtime.db").write_bytes(b"db")
            (root / "README.md").write_text("token sk-abcdefgh", encoding="utf-8")
            codes = {item["code"] for item in scan_tree(root, POLICY)}
        self.assertEqual(codes, {"FORBIDDEN_SUFFIX", "SECRET_PATTERN"})

    def test_rejects_closed_invalid_policy_and_non_directory_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_policies = [
                {key: value for key, value in POLICY.items() if key != "allowed_binary_suffixes"},
                {**POLICY, "unexpected": 1},
                {**POLICY, "minimum_phrase_tokens": False},
                {**POLICY, "private_source_roots": ["\x00"]},
                {**POLICY, "private_source_roots": ["relative/private"]},
                {**POLICY, "forbidden_path_fragments": ["\x01"]},
                {**POLICY, "secret_patterns": [".*"]},
            ]
            results = [scan_tree(root, policy) for policy in invalid_policies]
            invalid_root = scan_tree(root / "missing", POLICY)
        self.assertTrue(all(result[0]["code"] == "POLICY_INVALID" for result in results))
        self.assertEqual(invalid_root[0]["code"], "ROOT_INVALID")

    def test_rejects_unicode_control_and_format_policy_strings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = [
                scan_tree(root, {**POLICY, "forbidden_path_fragments": [chr(codepoint)]})
                for codepoint in (0x85, 0x202E)
            ]

        self.assertEqual([{item["code"] for item in result} for result in results], [{"POLICY_INVALID"}, {"POLICY_INVALID"}])

    def test_rejects_symlink_hidden_residue_and_unsafe_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hidden = root / FRAGMENT_GIT
            hidden.mkdir()
            (hidden / "config").write_text("x", encoding="utf-8")
            (root / "binary.txt").write_bytes(b"\x00payload")
            (root / "invalid.txt").write_bytes(b"\xff")
            target = root / "target.txt"
            target.write_text("x", encoding="utf-8")
            (root / "link.txt").symlink_to(target)
            codes = {item["code"] for item in scan_tree(root, POLICY)}
        self.assertTrue({"FORBIDDEN_PATH_FRAGMENT", "BINARY_CONTENT", "SYMLINK"} <= codes)

    def test_flags_empty_policy_declared_residue_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / FRAGMENT_CACHE).mkdir()
            findings = scan_tree(root, POLICY)
        self.assertIn(("FORBIDDEN_PATH_FRAGMENT", FRAGMENT_CACHE), {(item["code"], item["path"]) for item in findings})

    def test_binary_controls_require_casefolded_explicit_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "controls.bin").write_bytes(b"\x01\x02")
            (root / "allowed.BLOB").write_bytes(b"\x01\x02")
            findings = scan_tree(root, {**POLICY, "allowed_binary_suffixes": [".blob"]})
        self.assertIn(("BINARY_CONTENT", "controls.bin"), {(item["code"], item["path"]) for item in findings})
        self.assertNotIn("allowed.BLOB", {item["path"] for item in findings})

    def test_forbidden_fragment_matching_normalizes_and_casefolds_text_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / MIXED_NODE).mkdir()
            (root / "lower.txt").write_text("/" + "u" + "sers/private", encoding="utf-8")
            (root / "mixed.txt").write_text("/" + "uSeRs/private", encoding="utf-8")
            findings = scan_tree(root, POLICY)
        found = {(item["code"], item["path"]) for item in findings}
        self.assertTrue({
            ("FORBIDDEN_PATH_FRAGMENT", MIXED_NODE),
            ("FORBIDDEN_PATH_FRAGMENT", "lower.txt"),
            ("FORBIDDEN_PATH_FRAGMENT", "mixed.txt"),
        } <= found)

    def test_detects_synthetic_private_phrase_overlap(self) -> None:
        phrase = "cobalt lanterns drift silently above the temporary orchard after midnight rain today"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_source = root / "private-source.txt"
            candidate = root / "candidate"
            candidate.mkdir()
            private_source.write_text(phrase, encoding="utf-8")
            (candidate / "copied.txt").write_text(phrase, encoding="utf-8")
            findings = scan_tree(candidate, {**POLICY, "private_source_roots": [str(private_source)]})
        self.assertIn("PRIVATE_PHRASE_OVERLAP", {item["code"] for item in findings})

    def test_generic_paraphrase_does_not_match_private_phrase(self) -> None:
        source = "cobalt lanterns drift silently above the temporary orchard after midnight rain today"
        paraphrase = "Blue lamps float quietly over a short lived grove after a rainy late night."
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_source = root / "private-source.txt"
            candidate = root / "candidate"
            candidate.mkdir()
            private_source.write_text(source, encoding="utf-8")
            (candidate / "paraphrase.txt").write_text(paraphrase, encoding="utf-8")
            findings = scan_tree(candidate, {**POLICY, "private_source_roots": [str(private_source)]})
        self.assertNotIn("PRIVATE_PHRASE_OVERLAP", {item["code"] for item in findings})

    def test_private_errors_are_opaque_and_prefix_collisions_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            candidate = workspace / "candidate"
            private_root = workspace / "candidate-private"
            candidate.mkdir()
            private_root.mkdir()
            (private_root / "internal-name.bin").write_bytes(b"\x00x")
            findings = scan_tree(candidate, {**POLICY, "private_source_roots": [str(private_root)]})
        private_finding = next(item for item in findings if item["code"] == "PRIVATE_SOURCE_INVALID")
        self.assertTrue(private_finding["path"].startswith("private-root:0:sha256:"))
        self.assertNotIn("candidate-private", private_finding["path"] + private_finding["evidence"])
        self.assertNotIn("internal-name", private_finding["path"] + private_finding["evidence"])

    def test_findings_have_stable_shape_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "z.db").write_text("sk-abcdefgh", encoding="utf-8")
            (root / "a.db").write_text("sk-abcdefgh", encoding="utf-8")
            findings = scan_tree(root, POLICY)
        self.assertTrue(all(set(item) == {"code", "path", "evidence", "severity"} for item in findings))
        self.assertEqual(findings, sorted(findings, key=lambda item: (item["path"], item["code"], item["evidence"])))

    def test_cli_returns_structured_json_for_success_findings_and_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "candidate"
            root.mkdir()
            policy_path = workspace / "policy.json"
            policy_path.write_text(json.dumps(POLICY), encoding="utf-8")
            clean = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", "candidate", "--policy", "policy.json"],
                capture_output=True,
                check=False,
                cwd=workspace,
                text=True,
            )
            clean_reversed = subprocess.run(
                [sys.executable, str(SCRIPT), "--policy", "policy.json", "--root", "candidate"],
                capture_output=True,
                check=False,
                cwd=workspace,
                text=True,
            )
            (root / "runtime.db").write_text("x", encoding="utf-8")
            flagged = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--policy", str(policy_path)],
                capture_output=True,
                check=False,
                text=True,
            )
            bad_policy = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(root),
                    "--policy",
                    str(workspace / "missing.json"),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            invalid_utf8_policy = workspace / "invalid-policy.json"
            invalid_utf8_policy.write_bytes(b"\xff")
            invalid_utf8 = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--policy", str(invalid_utf8_policy)],
                capture_output=True,
                check=False,
                text=True,
            )
            unicode_controls = [chr(codepoint) for codepoint in (0x85, 0x202E)]
            control_results = []
            for index, control in enumerate(unicode_controls):
                control_policy = workspace / f"control-{index}.json"
                control_policy.write_text(json.dumps({**POLICY, "forbidden_path_fragments": [control]}), encoding="utf-8")
                control_results.append(
                    subprocess.run(
                        [sys.executable, str(SCRIPT), "--root", str(root), "--policy", str(control_policy)],
                        capture_output=True,
                        check=False,
                        text=True,
                    )
                )
        self.assertEqual(clean.returncode, 0)
        self.assertEqual(json.loads(clean.stdout), [])
        self.assertEqual(clean_reversed.returncode, 0)
        self.assertEqual(json.loads(clean_reversed.stdout), [])
        self.assertEqual(flagged.returncode, 1)
        self.assertTrue(json.loads(flagged.stdout))
        for result, code in ((bad_policy, "POLICY_INVALID"), (invalid_utf8, "POLICY_INVALID")):
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)[0]["code"], code)
            self.assertEqual(result.stderr, "")
        for control, result in zip(unicode_controls, control_results):
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)[0]["code"], "POLICY_INVALID")
            self.assertEqual(result.stderr, "")
            self.assertNotIn(control, result.stdout)

    def test_cli_rejects_every_noncanonical_argument_shape_as_json_only_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "candidate"
            root.mkdir()
            policy_path = workspace / "policy.json"
            policy_path.write_text(json.dumps(POLICY), encoding="utf-8")
            invalid_arguments = [
                [],
                ["candidate", "policy.json"],
                ["--root", "candidate"],
                ["--policy", "policy.json"],
                ["--root", "candidate", "--policy"],
                ["--root", "", "--policy", "policy.json"],
                ["--root", "candidate", "--policy", ""],
                ["--root", "candidate", "--root", "candidate", "--policy", "policy.json"],
                ["--root", "candidate", "--policy", "policy.json", "--policy", "policy.json"],
                ["--root", "candidate", "--policy", "policy.json", "--unknown", "value"],
                ["--help"],
                ["-h"],
                ["--root", "candidate", "--policy", "policy.json", "--help"],
            ]
            results = [
                subprocess.run(
                    [sys.executable, str(SCRIPT), *arguments],
                    capture_output=True,
                    check=False,
                    cwd=workspace,
                    text=True,
                )
                for arguments in invalid_arguments
            ]

        for result in results:
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(
                json.loads(result.stdout),
                [
                    {
                        "code": "CLI_USAGE",
                        "evidence": "required-named-flags-root-and-policy",
                        "path": "<cli>",
                        "severity": "CRITICAL",
                    }
                ],
            )
            self.assertEqual(result.stderr, "")

    def test_complete_candidate_self_scan_uses_live_policy_or_explicitly_skips(self) -> None:
        if not LIVE_POLICY.is_file():
            self.skipTest("external private policy is intentionally unavailable")
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            assemble(ROOT, candidate, manifest["entries"], strict=False)
            findings = scan_tree(
                candidate,
                json.loads(LIVE_POLICY.read_text(encoding="utf-8")),
            )
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
