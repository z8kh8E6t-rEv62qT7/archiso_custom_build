#!/usr/bin/env python3
"""Test archive/repository consistency and failed publication without pacman writes."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import aur_repo


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "localrepo/build-test/repo"
        self.repo.mkdir(parents=True)
        self.name = "rime-ice-pinyin-git"
        self.filename = f"{self.name}-r1.test-1-any.pkg.tar"
        self.create_repo()

    def write_tar(self, path, filename, content):
        self.write_archive(path, {filename: content})

    def write_archive(self, path, entries):
        with tarfile.open(path, "w:gz" if str(path).endswith(".gz") else "w") as archive:
            for filename, content in entries.items():
                data = content.encode()
                entry = tarfile.TarInfo(filename)
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))

    def create_repo(self, name="rime-ice-pinyin-git", arch="any"):
        records = {}
        entries = {}
        for expected_name in aur_repo.PACKAGES:
            actual_name = name if expected_name == self.name else expected_name
            package_arch = arch if expected_name == self.name else "x86_64"
            filename = (self.filename if expected_name == self.name else
                        f"{expected_name}-r1.test-1-{package_arch}.pkg.tar")
            self.write_tar(self.repo / filename, ".PKGINFO",
                           f"pkgname = {actual_name}\npkgver = r1.test-1\narch = {package_arch}\n")
            checksum = aur_repo.digest(self.repo / filename)
            fields = {"NAME": actual_name, "VERSION": "r1.test-1", "ARCH": package_arch,
                      "FILENAME": filename, "SHA256SUM": checksum}
            entries[f"{expected_name}/desc"] = "\n\n".join(
                f"%{k}%\n{v}" for k, v in fields.items()) + "\n\n"
            records[expected_name] = {"filename": filename, "version": "r1.test-1", "sha256": checksum}
        self.write_archive(self.repo / aur_repo.DATABASE, entries)
        link = self.repo / "custom-aur.db"
        if not link.is_symlink():
            link.symlink_to(aur_repo.DATABASE)
        self.manifest = {"packages": records,
                         "database_sha256": aur_repo.digest(self.repo / aur_repo.DATABASE)}
        self.save_manifest()

    def save_manifest(self):
        (self.repo / "manifest.json").write_text(json.dumps(self.manifest))

    def test_valid(self):
        self.assertEqual(aur_repo.validate(self.repo), self.repo)

    def test_missing_package(self):
        (self.repo / self.filename).unlink()
        with self.assertRaises(OSError):
            aur_repo.validate(self.repo)

    def test_corrupt_package(self):
        with (self.repo / self.filename).open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "校验和"):
            aur_repo.validate(self.repo)

    def test_wrong_name_and_architecture(self):
        for name, arch in [("unrelated", "any"), (self.name, "aarch64")]:
            with self.subTest(name=name, arch=arch):
                self.create_repo(name, arch)
                with self.assertRaisesRegex(ValueError, "包名或架构"):
                    aur_repo.validate(self.repo)

    def test_mismatched_database(self):
        self.write_archive(self.repo / aur_repo.DATABASE,
                           {"package/desc": "%NAME%\nunrelated\n\n",
                            "other/desc": "%NAME%\nunrelated\n\n"})
        self.manifest["database_sha256"] = aur_repo.digest(self.repo / aur_repo.DATABASE)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "不一致|只包含"):
            aur_repo.validate(self.repo)

    def test_publish_failure_preserves_current(self):
        previous_root = aur_repo.ROOT
        aur_repo.ROOT = self.root
        self.addCleanup(setattr, aur_repo, "ROOT", previous_root)
        current = self.root / "localrepo/current"
        current.symlink_to("previous/repo")
        self.create_repo(name="unrelated")
        with self.assertRaises(ValueError):
            aur_repo.publish(self.repo, self.publish_packages())
        self.assertEqual(current.readlink(), Path("previous/repo"))

    def test_publish_success(self):
        previous_root = aur_repo.ROOT
        aur_repo.ROOT = self.root
        self.addCleanup(setattr, aur_repo, "ROOT", previous_root)
        aur_repo.publish(self.repo, self.publish_packages())
        self.assertEqual(aur_repo.validate(self.root / "localrepo/current"), self.repo)

    def publish_packages(self):
        return [(record["filename"], "aur-test", "upstream-test" if name == self.name else "")
                for name, record in self.manifest["packages"].items()]

    def test_incomplete_manifest(self):
        del self.manifest["packages"][self.name]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "必须包含"):
            aur_repo.validate(self.repo)

    def test_duplicate_database_entries(self):
        with tarfile.open(self.repo / aur_repo.DATABASE) as archive:
            description = archive.extractfile(f"{self.name}/desc").read().decode()
        self.write_archive(self.repo / aur_repo.DATABASE,
                           {"package/desc": description, "duplicate/desc": description})
        self.manifest["database_sha256"] = aur_repo.digest(self.repo / aur_repo.DATABASE)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "不一致|只包含"):
            aur_repo.validate(self.repo)


if __name__ == "__main__":
    unittest.main()
