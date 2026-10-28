import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

SPEC = importlib.util.spec_from_file_location(
    "package_publisher", Path(__file__).parents[1] / "scripts/publish-package-bundle.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PackagePublisherTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.jar = b"original jar"
        self.pom = b'''<project xmlns="http://maven.apache.org/POM/4.0.0">
<modelVersion>4.0.0</modelVersion><groupId>org.example</groupId><artifactId>sample</artifactId>
<version>1.0.0</version><distributionManagement><repository><id>github</id>
<url>https://maven.pkg.github.com/caulis/example</url></repository></distributionManagement></project>'''
        self.relative = "org/example/sample/1.0.0/sample-1.0.0"
        self.files = {}
        self.artifact = {"groupId": "org.example", "artifactId": "sample", "version": "1.0.0", "packaging": "jar", "files": []}
        for extension, content in (("pom", self.pom), ("jar", self.jar)):
            path = "artifacts/" + self.relative + "." + extension
            self.files[path] = content
            sha = hashlib.sha256(content).hexdigest()
            file = {"path": path, "sha256": sha, "size": len(content), "sourceSha256": sha, "extension": extension, "classifier": ""}
            if extension == "pom":
                file["sourcePath"] = "originals/" + self.relative + ".pom"
                self.files[file["sourcePath"]] = content
            self.artifact["files"].append(file)
        self.manifest = {"schemaVersion": 1, "targetRepository": "caulis/example", "artifacts": [self.artifact]}

    def archive(self):
        path = self.root / "bundle.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(self.manifest))
            for name, content in self.files.items():
                archive.writestr(name, content)
        return path, publisher.digest(path)

    def validate(self):
        path, checksum = self.archive()
        return publisher.validate_bundle(path, checksum, "caulis/example", self.root / "extracted")

    def test_valid_bundle_preserves_jar(self):
        result = self.validate()
        self.assertEqual(result, self.manifest)
        self.assertEqual((self.root / "extracted" / ("artifacts/" + self.relative + ".jar")).read_bytes(), self.jar)

    def test_wrong_bundle_hash_rejected(self):
        path, _ = self.archive()
        with self.assertRaisesRegex(publisher.PublishError, "SHA-256 mismatch"):
            publisher.validate_bundle(path, "0" * 64, "caulis/example", self.root)

    def test_wrong_target_rejected(self):
        self.manifest["targetRepository"] = "someone/else"
        with self.assertRaisesRegex(publisher.PublishError, "target repository"):
            self.validate()

    def test_changed_jar_rejected(self):
        self.files["artifacts/" + self.relative + ".jar"] = b"modified jar"
        with self.assertRaisesRegex(publisher.PublishError, "checksum or size"):
            self.validate()

    def test_archive_path_traversal_rejected(self):
        self.artifact["files"][0]["path"] = "../outside"
        with self.assertRaisesRegex(publisher.PublishError, "path does not match"):
            self.validate()
        self.assertFalse((self.root / "outside").exists())

    def test_unexpected_archive_entry_rejected(self):
        self.files["../outside"] = b"bad"
        with self.assertRaisesRegex(publisher.PublishError, "Unexpected"):
            self.validate()
        self.assertFalse((self.root / "outside").exists())

    def test_missing_main_jar_rejected(self):
        self.artifact["files"] = self.artifact["files"][:1]
        with self.assertRaisesRegex(publisher.PublishError, "main artifact"):
            self.validate()

    def test_mismatched_pom_rejected(self):
        path = self.root / "pom.xml"
        path.write_bytes(self.pom.replace(b"1.0.0", b"2.0.0"))
        with self.assertRaisesRegex(publisher.PublishError, "coordinate mismatch"):
            publisher.check_pom(path, self.artifact, "caulis/example")

    def test_personal_registry_rejected(self):
        path = self.root / "pom.xml"
        path.write_bytes(self.pom.replace(b"caulis/example", b"opaopa6969/example"))
        with self.assertRaisesRegex(publisher.PublishError, "different Packages owner"):
            publisher.check_pom(path, self.artifact, "caulis/example")

    def test_conflict_detected_before_any_write(self):
        deploy = mock.Mock()
        with self.assertRaisesRegex(publisher.PublishError, "Existing artifact differs"):
            publisher.publish(self.manifest, self.root, True, probe=lambda *args: "different", deployer=deploy)
        deploy.assert_not_called()

    def test_partial_publication_rejected(self):
        probe = mock.Mock(side_effect=[self.artifact["files"][0]["sha256"], None])
        with self.assertRaisesRegex(publisher.PublishError, "Partially published"):
            publisher.publication_plan(self.manifest, self.root, probe)

    def test_identical_existing_version_is_not_republished(self):
        deploy = mock.Mock()
        publisher.publish(self.manifest, self.root, True, probe=lambda repo, file, directory: file["sha256"], deployer=deploy)
        deploy.assert_not_called()

    def test_dry_run_does_not_publish(self):
        deploy = mock.Mock()
        publisher.publish(self.manifest, self.root, probe=lambda *args: None, deployer=deploy)
        deploy.assert_not_called()

    def test_new_version_is_verified_after_publish(self):
        deploy = mock.Mock()
        probe = mock.Mock(side_effect=[None, None] + [f["sha256"] for f in self.artifact["files"]])
        publisher.publish(self.manifest, self.root, True, probe, deploy)
        deploy.assert_called_once_with(self.artifact, "caulis/example", self.root)
        self.assertEqual(probe.call_count, 4)

    def test_corrupted_publication_fails(self):
        probe = mock.Mock(side_effect=[None, None, "different"])
        with self.assertRaisesRegex(publisher.PublishError, "verification failed"):
            publisher.publish(self.manifest, self.root, True, probe, mock.Mock())


if __name__ == "__main__":
    unittest.main()
