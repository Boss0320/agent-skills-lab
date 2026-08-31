from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unicodedata
import unittest

from scripts.assemble_public_candidate import (
    AssemblyError,
    assemble,
    validate_relative_path,
)

GIT_DIRECTORY = "." + "git"
GITIGNORE_NAME = GIT_DIRECTORY + "ignore"


def manifest_entry(path: Path, relative_path: str) -> dict[str, object]:
    return {
        "path": relative_path,
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


class PublicAssemblerTests(unittest.TestCase):
    def test_allows_only_the_approved_root_dotfile(self) -> None:
        self.assertEqual(Path(GITIGNORE_NAME), validate_relative_path(GITIGNORE_NAME))

        for unsafe_path in (
            ".env",
            f"{GIT_DIRECTORY}/config",
            f"nested/{GIT_DIRECTORY}/config",
            f"x{GITIGNORE_NAME}",
            f"nested/{GITIGNORE_NAME}",
            ".DS_Store",
        ):
            with self.subTest(unsafe_path=unsafe_path):
                with self.assertRaises(AssemblyError):
                    validate_relative_path(unsafe_path)

    def test_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            with self.assertRaises(AssemblyError):
                assemble(
                    Path(source),
                    Path(destination) / "fresh",
                    [{"path": "../private.txt", "size": 1, "sha256": "0" * 64}],
                )

    def test_rejects_absolute_hidden_and_noncanonical_paths(self) -> None:
        for unsafe_path in (
            "/private.txt",
            ".env",
            "docs/.draft.md",
            "docs//readme.md",
            "C:/private.txt",
            "C:private.txt",
            "C:",
            "D:docs/readme.md",
            ".",
            "./README.md",
            "README.md/.",
        ):
            with self.subTest(unsafe_path=unsafe_path):
                with self.assertRaises(AssemblyError):
                    validate_relative_path(unsafe_path)

    def test_copies_only_digest_bound_file(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            payload = root / "README.md"
            payload.write_text("safe\n", encoding="utf-8")

            result = assemble(
                root,
                Path(destination) / "fresh",
                [manifest_entry(payload, "README.md")],
            )

            copied = Path(destination) / "fresh" / "README.md"
            self.assertEqual(result["copied_files"], 1)
            self.assertEqual(copied.read_bytes(), b"safe\n")

    def test_rejects_unlisted_source_file_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            listed = root / "README.md"
            listed.write_text("safe\n", encoding="utf-8")
            (root / "unlisted.txt").write_text("private\n", encoding="utf-8")

            with self.assertRaisesRegex(AssemblyError, r"^unlisted source file: unlisted\.txt$"):
                assemble(
                    root,
                    Path(destination) / "fresh",
                    [manifest_entry(listed, "README.md")],
                )

    def test_rejects_unreadable_descendant_before_creating_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            listed = source / "README.md"
            listed.write_text("safe\n", encoding="utf-8")
            blocked = source / "blocked"
            blocked.mkdir()
            (blocked / "private.txt").write_text("private\n", encoding="utf-8")
            destination = root / "out" / "fresh"
            destination.parent.mkdir()
            blocked.chmod(0)
            try:
                self.assertFalse(os.access(blocked, os.R_OK | os.X_OK))
                with self.assertRaises(AssemblyError):
                    assemble(source, destination, [manifest_entry(listed, "README.md")])
                self.assertFalse(destination.exists())
            finally:
                blocked.chmod(0o700)

    def test_non_strict_mode_leaves_unlisted_source_file_out_of_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            listed = root / "README.md"
            listed.write_text("safe\n", encoding="utf-8")
            (root / "unlisted.txt").write_text("private\n", encoding="utf-8")

            assemble(
                root,
                Path(destination) / "fresh",
                [manifest_entry(listed, "README.md")],
                strict=False,
            )

            self.assertFalse((Path(destination) / "fresh" / "unlisted.txt").exists())

    def test_rejects_duplicate_or_ambiguous_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            payload = root / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            entry = manifest_entry(payload, "README.md")

            with self.assertRaises(AssemblyError):
                assemble(root, Path(destination) / "fresh", [entry, dict(entry)])

    def test_rejects_casefolded_aliases_in_directory_segments(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            payload = root / "Docs" / "README.md"
            payload.parent.mkdir()
            payload.write_text("safe\n", encoding="utf-8")

            with self.assertRaises(AssemblyError):
                assemble(
                    root,
                    Path(destination) / "fresh",
                    [
                        manifest_entry(payload, "Docs/README.md"),
                        manifest_entry(payload, "docs/readme.md"),
                    ],
                    strict=False,
                )

    def test_rejects_nfc_nfd_manifest_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            nfc_name = "évidence.txt"
            nfd_name = unicodedata.normalize("NFD", nfc_name)
            payload = root / nfc_name
            payload.write_text("safe\n", encoding="utf-8")

            with self.assertRaises(AssemblyError):
                assemble(
                    root,
                    Path(destination) / "fresh",
                    [manifest_entry(payload, nfc_name), manifest_entry(payload, nfd_name)],
                    strict=False,
                )

    def test_rejects_malformed_manifest_entries(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            cases = (
                {"path": "README.md", "size": 1},
                {"path": "README.md", "size": True, "sha256": "0" * 64},
                {"path": 3, "size": 1, "sha256": "0" * 64},
                {"path": "README.md", "size": 1, "sha256": "not-a-digest"},
                {"path": "README.md", "size": 1, "sha256": "0" * 64, "extra": "no"},
            )
            for entry in cases:
                with self.subTest(entry=entry):
                    with self.assertRaises(AssemblyError):
                        assemble(root, Path(destination) / "fresh", [entry])

    def test_rejects_size_or_digest_mismatch_without_creating_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            payload = root / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            entry = manifest_entry(payload, "README.md")
            entry["size"] = 999
            target = Path(destination) / "fresh"

            with self.assertRaises(AssemblyError):
                assemble(root, target, [entry])

            self.assertFalse(target.exists())

    def test_rejects_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            payload = root / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            target = Path(destination) / "fresh"
            target.mkdir()

            with self.assertRaises(AssemblyError):
                assemble(root, target, [manifest_entry(payload, "README.md")])

    def test_rejects_source_symlink_even_when_not_listed(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            payload = root / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            os.symlink(payload, root / "linked-readme.md")

            with self.assertRaises(AssemblyError):
                assemble(root, Path(destination) / "fresh", [manifest_entry(payload, "README.md")])

    def test_rejects_source_root_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            payload = source / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            alias = root / "source-alias"
            alias.symlink_to(source, target_is_directory=True)
            destination = root / "out"
            destination.mkdir()

            with self.assertRaises(AssemblyError):
                assemble(alias, destination / "fresh", [manifest_entry(payload, "README.md")])

    def test_rejects_source_root_symlink_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "real"
            source = real / "source"
            source.mkdir(parents=True)
            payload = source / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            alias = root / "source-alias"
            alias.symlink_to(real, target_is_directory=True)
            destination = root / "out"
            destination.mkdir()
            target = destination / "fresh"

            with self.assertRaises(AssemblyError):
                assemble(alias / "source", target, [manifest_entry(payload, "README.md")])
            self.assertFalse(target.exists())

    def test_rejects_destination_parent_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            payload = source / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            real_parent = root / "real-parent"
            real_parent.mkdir()
            alias = root / "destination-alias"
            alias.symlink_to(real_parent, target_is_directory=True)

            with self.assertRaises(AssemblyError):
                assemble(source, alias / "fresh", [manifest_entry(payload, "README.md")])

    def test_rejects_destination_root_symlink_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            payload = source / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            real = root / "real"
            real.mkdir()
            (real / "nested").mkdir()
            alias = root / "destination-alias"
            alias.symlink_to(real, target_is_directory=True)
            target = alias / "nested" / "fresh"

            with self.assertRaises(AssemblyError):
                assemble(source, target, [manifest_entry(payload, "README.md")])
            self.assertFalse((real / "nested" / "fresh").exists())

    def test_allows_fixed_system_temp_ancestor(self) -> None:
        with tempfile.TemporaryDirectory(dir="/tmp") as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            payload = source / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            target = root / "fresh"

            result = assemble(source, target, [manifest_entry(payload, "README.md")])

            self.assertEqual(result["copied_files"], 1)
            self.assertEqual((target / "README.md").read_bytes(), b"safe\n")

    def test_rejects_listed_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            root = Path(source)
            payload = root / "README.md"
            payload.write_text("safe\n", encoding="utf-8")
            linked = root / "linked-readme.md"
            os.symlink(payload, linked)

            with self.assertRaises(AssemblyError):
                assemble(root, Path(destination) / "fresh", [manifest_entry(payload, "linked-readme.md")])


if __name__ == "__main__":
    unittest.main()
