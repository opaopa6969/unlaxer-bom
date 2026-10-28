import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

SPEC = importlib.util.spec_from_file_location(
    "package_bundle", Path(__file__).parents[1] / "scripts/prepare-package-bundle.py")
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class PackageBundleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.coordinate = {"groupId": "org.unlaxer", "artifactId": "example", "version": "1.2.3", "source": "unlaxer-bom"}
        self.pom = b'''<project xmlns="http://maven.apache.org/POM/4.0.0">
<modelVersion>4.0.0</modelVersion><groupId>org.unlaxer</groupId><artifactId>example</artifactId><version>1.2.3</version>
<!-- Keep provenance and BOM registry comments. -->
<scm><url>https://github.com/opaopa6969/example</url></scm>
<repositories><repository><id>github</id><url>https://maven.pkg.github.com/opaopa6969/unlaxer-bom</url></repository></repositories>
<distributionManagement><repository><id>github</id><url>https://maven.pkg.github.com/opaopa6969/example</url></repository></distributionManagement>
</project>'''

    def fetch(self, url, destination, optional=False):
        if optional:
            return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.pom if url.endswith(".pom") else b"original-jar-bytes")
        return True

    def prepare(self):
        return bundle.prepare_bundle([self.coordinate], "caulis/unlaxer-bom", self.root / "result.zip", self.fetch)

    def test_preserves_jar_and_original_pom_with_checksums(self):
        result = self.prepare()
        with zipfile.ZipFile(self.root / "result.zip") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            for file in manifest["artifacts"][0]["files"]:
                self.assertEqual(hashlib.sha256(archive.read(file["path"])).hexdigest(), file["sha256"])
                if file["extension"] == "jar":
                    self.assertEqual(archive.read(file["path"]), b"original-jar-bytes")
                else:
                    self.assertEqual(archive.read(file["sourcePath"]), self.pom)
        self.assertEqual(result["bundleSha256"], bundle.digest(self.root / "result.zip"))

    def test_changes_registry_owner_without_rewriting_source_history(self):
        self.prepare()
        with zipfile.ZipFile(self.root / "result.zip") as archive:
            pom = archive.read("artifacts/org/unlaxer/example/1.2.3/example-1.2.3.pom").decode()
        self.assertNotIn("maven.pkg.github.com/opaopa6969", pom)
        self.assertIn("maven.pkg.github.com/caulis/unlaxer-bom", pom)
        self.assertIn("github.com/opaopa6969/example", pom)
        self.assertIn("Keep provenance", pom)

    def test_download_failure_leaves_no_partial_bundle(self):
        def fail(url, destination, optional=False):
            raise bundle.BundleError("HTTP 403")
        with self.assertRaises(bundle.BundleError):
            bundle.prepare_bundle([self.coordinate], "caulis/unlaxer-bom", self.root / "result.zip", fail)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_mismatched_version_is_rejected(self):
        self.coordinate["version"] = "1.2.4"
        with self.assertRaisesRegex(bundle.BundleError, "version mismatch"):
            self.prepare()
        self.assertFalse((self.root / "result.zip").exists())

    def test_mutable_snapshot_is_rejected_before_download(self):
        self.coordinate["version"] = "1.2.3-SNAPSHOT"
        with self.assertRaisesRegex(bundle.BundleError, "immutable"):
            self.prepare()

    def test_duplicate_coordinates_are_rejected(self):
        with self.assertRaisesRegex(bundle.BundleError, "unique"):
            bundle.prepare_bundle([self.coordinate] * 2, "caulis/unlaxer-bom", self.root / "result.zip", self.fetch)

    def test_path_traversal_is_rejected(self):
        self.coordinate["artifactId"] = "../../other"
        with self.assertRaisesRegex(bundle.BundleError, "Invalid"):
            self.prepare()

    def test_existing_bundle_is_not_overwritten(self):
        self.prepare()
        original = (self.root / "result.zip").read_bytes()
        with self.assertRaisesRegex(bundle.BundleError, "already exists"):
            self.prepare()
        self.assertEqual((self.root / "result.zip").read_bytes(), original)

    def test_pom_only_artifact_has_no_jar_download(self):
        self.pom = self.pom.replace(b"</project>", b"<packaging>pom</packaging></project>")
        fetch = mock.Mock(side_effect=self.fetch)
        result = bundle.prepare_bundle([self.coordinate], "caulis/unlaxer-bom", self.root / "result.zip", fetch)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["artifacts"][0]["packaging"], "pom")

    def test_inherited_group_and_version_are_validated(self):
        self.pom = self.pom.replace(
            b"<groupId>org.unlaxer</groupId><artifactId>example</artifactId><version>1.2.3</version>",
            b"<parent><groupId>org.unlaxer</groupId><artifactId>parent</artifactId><version>1.2.3</version></parent><artifactId>example</artifactId>")
        self.assertEqual(self.prepare()["artifacts"][0]["version"], "1.2.3")

    def test_source_auth_is_not_in_arguments_or_forwarded_on_redirect(self):
        with mock.patch.dict(bundle.os.environ, {"GITHUB_PACKAGES_TOKEN": "test-secret"}), \
                mock.patch.object(bundle.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="200")) as run:
            bundle.download("https://maven.pkg.github.com/opaopa6969/unlaxer-bom/file.pom", self.root / "pom")
        command = run.call_args.args[0]
        self.assertNotIn("test-secret", " ".join(command))
        self.assertNotIn("--location-trusted", command)
        self.assertIn("--disable", command)
        self.assertIn("test-secret", run.call_args.kwargs["input"])

    def test_central_has_no_auth_and_optional_forbidden_is_fatal(self):
        with mock.patch.dict(bundle.os.environ, {"GITHUB_PACKAGES_TOKEN": "test-secret"}), \
                mock.patch.object(bundle.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="403")) as run:
            with self.assertRaisesRegex(bundle.BundleError, "HTTP 403"):
                bundle.download("https://repo.maven.apache.org/maven2/file.jar", self.root / "jar", optional=True)
        self.assertEqual(run.call_args.kwargs["input"], "")


if __name__ == "__main__":
    unittest.main()
