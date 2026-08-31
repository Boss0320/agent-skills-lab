from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "evidence" / "benchmark-summary.json"
RESULT_SHA256 = "3c7c398cfb98dcb215dd20b1db928a82d4fb87262adbba0b5ab20206de0194a4"
SUMMARY_SHA256 = "28401ee45ebd933cfb03415e3e751af56bb0313ca7869c187756d77174f24227"
MANIFEST_PATH = ROOT / "provenance" / "public-manifest.json"
GIT_DIRECTORY = "." + "git"
GITIGNORE_NAME = GIT_DIRECTORY + "ignore"
CACHE_DIRECTORY = "__py" + "cache__"
RIGHTS_NOTICE = """Copyright (c) 2026 Titus Lai. All rights reserved.

This repository is provided for portfolio review and evaluation only. You may
view, clone, and run it locally to evaluate the author's work. No permission is
granted to reuse, modify, redistribute, or incorporate any part of this
repository into other software, products, services, or publications, commercial
or otherwise, without prior written permission from the author.
"""


class PublicationEvidenceContractTests(unittest.TestCase):
    def test_benchmark_summary_has_exact_bounded_results(self) -> None:
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "schema_version",
                "evaluation_state",
                "claims_gate",
                "source_receipts",
                "conditions",
                "skills",
                "public_claim",
                "unsupported_claims",
            },
            set(summary),
        )
        self.assertEqual("agent-skills-lab-benchmark-summary/v1", summary["schema_version"])
        self.assertEqual("OFFLINE_REGRADE_COMPLETE", summary["evaluation_state"])
        self.assertEqual("EXPAND_BEFORE_PUBLIC_CLAIMS", summary["claims_gate"])
        self.assertEqual(
            {
                "preserved_result_receipts": 25,
                "new_model_calls": 0,
                "result_sha256": RESULT_SHA256,
            },
            summary["source_receipts"],
        )
        self.assertEqual(
            {
                "dataset": "frozen synthetic paired set",
                "paired_runs_per_case": 1,
                "regrade": "offline preserved-artifact quality regrade",
                "size_policy": "telemetry only",
            },
            summary["conditions"],
        )

        skills = {item["skill_id"]: item for item in summary["skills"]}
        self.assertEqual(
            {
                "agent-system-integration-audit",
                "dual-lens-investment-review",
                "ai-anime-production-director",
            },
            set(skills),
        )
        expected = {
            "agent-system-integration-audit": {
                "verdict": "LIMITED_ADVANCE",
                "primary_metric": "professional_packet_quality",
                "without_skill": "0/3",
                "with_skill": "2/3",
                "secondary_metric": "semantic_detection",
                "secondary_without_skill": "3/3",
                "secondary_with_skill": "3/3",
            },
            "dual-lens-investment-review": {
                "verdict": "ADVANCE",
                "primary_metric": "valid_lens_delivery",
                "without_skill": "0/6",
                "with_skill": "6/6",
                "secondary_metric": "reconciliation",
                "secondary_without_skill": "0/3",
                "secondary_with_skill": "3/3",
            },
            "ai-anime-production-director": {
                "verdict": "LIMITED_ADVANCE",
                "primary_metric": "valid_storyboard_workflow_artifact",
                "without_skill": "0/2",
                "with_skill": "2/2",
                "secondary_metric": "blind_preference",
                "secondary_without_skill": "unavailable",
                "secondary_with_skill": "unavailable",
            },
        }
        for skill_id, measured in expected.items():
            self.assertEqual(
                {"skill_id", "verdict", "measured", "not_proven"},
                set(skills[skill_id]),
                skill_id,
            )
            self.assertEqual(measured.pop("verdict"), skills[skill_id]["verdict"], skill_id)
            self.assertEqual(measured, skills[skill_id]["measured"], skill_id)
            self.assertTrue(skills[skill_id]["not_proven"], skill_id)

        unsupported = set(summary["unsupported_claims"])
        self.assertEqual(
            {
                "general intelligence uplift",
                "statistically strong public benchmark",
                "raw reasoning lift for Skill B",
                "finished media quality",
                "investment performance",
                "production certification",
            },
            unsupported,
        )

    def test_bilingual_copy_reports_results_without_generalizing_them(self) -> None:
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        status = (ROOT / "PUBLICATION_STATUS.md").read_text(encoding="utf-8")

        for text in (en, zh):
            for score in ("0/3 → 2/3", "3/3 → 3/3", "0/6 → 6/6", "0/3 → 3/3", "0/2 → 2/2"):
                self.assertIn(score, text)
            self.assertIn("EXPAND_BEFORE_PUBLIC_CLAIMS", text)
            self.assertIn("evidence/benchmark-summary.json", text)

        self.assertIn("Raw reasoning lift was not scored", en)
        self.assertIn("Finished-media quality remains unproven", en)
        self.assertIn("沒有評分自由推理能力是否提升", zh)
        self.assertIn("尚未證明最終成片品質", zh)
        self.assertNotIn("review-reliability lift is unproven", en)
        self.assertNotIn("審查可靠度提升尚未證明", zh)

        self.assertIn("- State: `LOCAL_CANDIDATE / LIMITED EVALUATION EVIDENCE`", status)
        self.assertIn(
            "- Public status: `PRIVATE_REMOTE — public toggle pending owner (2026-08-31)`",
            status,
        )
        self.assertIn("- Claims gate: `EXPAND_BEFORE_PUBLIC_CLAIMS`", status)
        self.assertIn("- Approved GitHub slug: `agent-skills-lab`", status)
        self.assertIn("- Rights: `ALL RIGHTS RESERVED / PORTFOLIO EVALUATION ONLY`", status)
        self.assertIn("224 standard-library tests, 0 failures, 0 errors", status)
        self.assertIn("manifest-assembled candidate private-policy scan returned `[]`", status)
        self.assertIn("155 content entries", status)
        self.assertIn("Live-tree manifest coverage: `PASS` — exact file-set equality", status)
        self.assertIn("2026-08-30 | Candidate snapshot before Git initialization", status)
        self.assertIn("2026-08-31 | Git initialized; private GitHub remote created", status)

    def test_public_copy_avoids_abstract_or_overbroad_origin_claims(self) -> None:
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        notices = (ROOT / "provenance" / "third-party-notices.md").read_text(encoding="utf-8")
        normalized_notices = " ".join(notices.split())
        self.assertIn("Three reusable workflow packages for AI work", en)
        self.assertNotIn("operating systems for AI work", en)
        self.assertIn("Current inventory found no bundled third-party source code", normalized_notices)
        self.assertIn(
            "Raw evaluation transcripts and preserved subject-model outputs are excluded",
            normalized_notices,
        )
        self.assertNotIn("source code, model output", normalized_notices)

    def test_provenance_binds_approved_slug_evidence_and_rights(self) -> None:
        provenance = json.loads(
            (ROOT / "provenance" / "revision-provenance.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {
                "schema_version",
                "revision",
                "state",
                "repository",
                "evidence",
                "rights",
                "entries",
            },
            set(provenance),
        )
        self.assertEqual("agent-skills-lab-revision-provenance/v3", provenance["schema_version"])
        self.assertEqual("private-remote-publication-2026-08-31", provenance["revision"])
        self.assertEqual("LOCAL_CANDIDATE_RIGHTS_APPROVED", provenance["state"])
        self.assertEqual(
            {
                "approved_slug": "agent-skills-lab",
                "git_state": "INITIALIZED",
                "remote_state": "PRIVATE_GITHUB",
                "public_status": "PENDING_OWNER_TOGGLE",
            },
            provenance["repository"],
        )
        self.assertEqual(
            {
                "aggregate_path": "evidence/benchmark-summary.json",
                "aggregate_sha256": SUMMARY_SHA256,
                "source_result_sha256": RESULT_SHA256,
                "claims_gate": "EXPAND_BEFORE_PUBLIC_CLAIMS",
            },
            provenance["evidence"],
        )
        self.assertEqual(
            {
                "status": "ALL_RIGHTS_RESERVED_PORTFOLIO_EVALUATION_ONLY",
                "license_path": "LICENSE",
                "third_party_notice_path": "provenance/third-party-notices.md",
            },
            provenance["rights"],
        )
        serialized = json.dumps(provenance)
        self.assertNotIn("/" + "Users" + "/", serialized)
        self.assertNotIn("/private/tmp", serialized)

        notices = (ROOT / "provenance" / "third-party-notices.md").read_text(encoding="utf-8")
        self.assertIn("view, clone, and run", notices)
        self.assertIn("No permission is granted to reuse", notices)
        self.assertIn("Python standard library", notices)
        self.assertIn("not legal advice", notices)
        self.assertEqual(RIGHTS_NOTICE, (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_bilingual_readmes_publish_copyable_two_run_verification(self) -> None:
        command = "python3 -m unittest discover -s tests"
        for path in (ROOT / "README.md", ROOT / "README.zh-TW.md"):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Verify locally", text)
                self.assertEqual(2, text.count(command))
                self.assertIn(f"```sh\n{command}\n{command}\n```", text)

    def test_public_manifest_exactly_covers_candidate_bytes(self) -> None:
        from scripts.assemble_public_candidate import assemble
        from scripts.build_public_manifest import manifest_for

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "schema_version": "agent-skills-lab-public-manifest/v1",
                "revision": "private-remote-publication-2026-08-31",
                "self_entry": "excluded_by_design",
            },
            {key: manifest[key] for key in ("schema_version", "revision", "self_entry")},
        )
        paths = [entry["path"] for entry in manifest["entries"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn(GITIGNORE_NAME, paths)
        self.assertNotIn("provenance/public-manifest.json", paths)
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            result = assemble(ROOT, candidate, manifest["entries"], strict=False)
            self.assertEqual(result["copied_files"], len(paths))
            candidate_manifest_path = candidate / "provenance" / "public-manifest.json"
            self.assertEqual(manifest, manifest_for(candidate, candidate_manifest_path))
            for entry in manifest["entries"]:
                self.assertEqual({"path", "size", "sha256"}, set(entry))
                path = candidate / entry["path"]
                self.assertTrue(path.is_file(), entry["path"])
                self.assertFalse(path.is_symlink(), entry["path"])
                payload = path.read_bytes()
                self.assertEqual(len(payload), entry["size"], entry["path"])
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(),
                    entry["sha256"],
                    entry["path"],
                )

    def test_live_tree_coverage_is_manifest_exact_except_fixed_residue(self) -> None:
        from scripts.assemble_public_candidate import assemble
        from scripts import build_public_manifest

        coverage_paths = getattr(build_public_manifest, "live_tree_coverage_paths", None)
        self.assertIsNotNone(coverage_paths, "live-tree coverage gate is missing")
        assert coverage_paths is not None

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest_self = "provenance/public-manifest.json"
        expected = {entry["path"] for entry in manifest["entries"]} | {manifest_self}
        self.assertEqual(expected, set(coverage_paths(ROOT)))

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            assemble(ROOT, candidate, manifest["entries"], strict=False)
            candidate_manifest = candidate / manifest_self
            candidate_manifest.write_bytes(MANIFEST_PATH.read_bytes())

            git_metadata = candidate / GIT_DIRECTORY
            git_metadata.mkdir()
            (git_metadata / "config").write_text("ignored\n", encoding="utf-8")
            cache = candidate / "tests" / CACHE_DIRECTORY
            cache.mkdir()
            (cache / "module.pyc").write_bytes(b"ignored")
            (candidate / "root.pyc").write_bytes(b"ignored")
            (candidate / ".DS_Store").write_bytes(b"ignored")
            self.assertEqual(expected, set(coverage_paths(candidate)))

            for relative_path in ("stray.txt", ".env", f"nested/{GITIGNORE_NAME}"):
                with self.subTest(relative_path=relative_path):
                    extra = candidate / relative_path
                    extra.parent.mkdir(parents=True, exist_ok=True)
                    extra.write_text("unmanifested\n", encoding="utf-8")
                    actual = set(coverage_paths(candidate))
                    self.assertEqual({relative_path}, actual - expected)
                    self.assertEqual(set(), expected - actual)
                    extra.unlink()

    def test_manifest_builder_rejects_symlinks_and_generated_residue(self) -> None:
        from scripts.build_public_manifest import ManifestError, build_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "provenance").mkdir()
            target = root / "README.md"
            target.write_text("safe\n", encoding="utf-8")
            (root / "linked.md").symlink_to(target)
            with self.assertRaisesRegex(ManifestError, "symlink"):
                build_manifest(root, root / "provenance" / "public-manifest.json")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "provenance").mkdir()
            (root / "module.pyc").write_bytes(b"residue")
            with self.assertRaisesRegex(ManifestError, "residue"):
                build_manifest(root, root / "provenance" / "public-manifest.json")

        for residue_name in (GIT_DIRECTORY, CACHE_DIRECTORY):
            with self.subTest(residue_name=residue_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "provenance").mkdir()
                residue = root / residue_name
                residue.mkdir()
                (residue / "payload").write_text("residue\n", encoding="utf-8")
                with self.assertRaisesRegex(ManifestError, "residue"):
                    build_manifest(root, root / "provenance" / "public-manifest.json")


if __name__ == "__main__":
    unittest.main()
