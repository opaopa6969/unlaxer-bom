import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-bom-version-drift.py"
SPEC = importlib.util.spec_from_file_location("check_bom_version_drift", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(checker)


def pom(body: str, properties: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>example</groupId><artifactId>test</artifactId><version>1</version>
  {properties}
  {body}
</project>
"""


class BomDriftTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bom = self.root / "bom.xml"
        self.bom.write_text(
            pom(
                """<dependencyManagement><dependencies>
                  <dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId>
                    <version>${parser.version}</version></dependency>
                </dependencies></dependencyManagement>""",
                "<properties><base.version>2.0</base.version>"
                "<parser.version>${base.version}</parser.version></properties>",
            ),
            encoding="utf-8",
        )
        self.managed = checker.managed_versions(self.bom)

    def tearDown(self):
        self.temporary.cleanup()

    def check(self, dependencies: str, properties: str = ""):
        consumer = self.root / "consumer.xml"
        consumer.write_text(pom(f"<dependencies>{dependencies}</dependencies>", properties), encoding="utf-8")
        return checker.drift_messages(consumer, self.managed, display_path="consumer/pom.xml")

    def test_different_literal_version_is_drift_without_bom_import(self):
        messages = self.check(
            "<dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId>"
            "<version>1.9</version></dependency>"
        )
        self.assertEqual(1, len(messages))
        self.assertIn("明示 version=1.9; BOM=2.0", messages[0])

    def test_same_literal_version_is_allowed(self):
        self.assertEqual([], self.check(
            "<dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId>"
            "<version>2.0</version></dependency>"
        ))

    def test_missing_version_is_allowed(self):
        self.assertEqual([], self.check(
            "<dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId></dependency>"
        ))

    def test_unmanaged_coordinate_is_ignored(self):
        self.assertEqual([], self.check(
            "<dependency><groupId>org.other</groupId><artifactId>parser</artifactId>"
            "<version>1.9</version></dependency>"
        ))

    def test_consumer_property_is_resolved(self):
        self.assertEqual([], self.check(
            "<dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId>"
            "<version>${consumer.parser.version}</version></dependency>",
            "<properties><consumer.parser.version>2.0</consumer.parser.version></properties>",
        ))

    def test_unresolved_consumer_property_is_drift(self):
        messages = self.check(
            "<dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId>"
            "<version>${external.version}</version></dependency>"
        )
        self.assertEqual(1, len(messages))
        self.assertIn("解決不能", messages[0])

    def test_reasoned_exception_is_allowed(self):
        self.assertEqual([], self.check(
            "<dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId>"
            "<version>2.1</version><!-- bom 例外: unlaxer-bom #99 の先行検証 -->"
            "</dependency>"
        ))

    def test_empty_exception_is_not_allowed(self):
        self.assertEqual(1, len(self.check(
            "<dependency><groupId>org.unlaxer</groupId><artifactId>parser</artifactId>"
            "<version>2.1</version><!-- bom 例外: TODO -->"
            "</dependency>"
        )))

    def test_consumer_dependency_management_pin_is_checked(self):
        consumer = self.root / "consumer.xml"
        consumer.write_text(pom(
            "<dependencyManagement><dependencies><dependency>"
            "<groupId>org.unlaxer</groupId><artifactId>parser</artifactId><version>1.9</version>"
            "</dependency></dependencies></dependencyManagement>"
        ), encoding="utf-8")
        self.assertEqual(1, len(checker.drift_messages(consumer, self.managed)))

    def test_profile_dependency_is_checked(self):
        consumer = self.root / "consumer.xml"
        consumer.write_text(pom(
            "<profiles><profile><id>test</id><dependencies><dependency>"
            "<groupId>org.unlaxer</groupId><artifactId>parser</artifactId><version>1.9</version>"
            "</dependency></dependencies></profile></profiles>"
        ), encoding="utf-8")
        self.assertEqual(1, len(checker.drift_messages(consumer, self.managed)))


class EntryPointTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / ".git").mkdir()
        (self.root / "pom.xml").write_text(pom(
            "<dependencyManagement><dependencies><dependency>"
            "<groupId>org.unlaxer</groupId><artifactId>parser</artifactId><version>2.0</version>"
            "</dependency></dependencies></dependencyManagement>"
        ), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def consumer(self, version: str) -> str:
        return pom(
            "<dependencies><dependency><groupId>org.unlaxer</groupId>"
            f"<artifactId>parser</artifactId><version>{version}</version>"
            "</dependency></dependencies>"
        )

    def test_hook_rejects_proposed_drift_with_exit_2(self):
        path = self.root / "module" / "pom.xml"
        payload = {"tool_input": {"file_path": str(path), "content": self.consumer("1.9")}}
        previous_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(2, checker.run_hook(self.root / "pom.xml"))
        finally:
            sys.stdin = previous_stdin

    def test_staged_mode_reads_index_instead_of_worktree(self):
        (self.root / ".git").rmdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        module = self.root / "module"
        module.mkdir()
        consumer = module / "pom.xml"
        consumer.write_text(self.consumer("1.9"), encoding="utf-8")
        subprocess.run(["git", "add", "pom.xml", "module/pom.xml"], cwd=self.root, check=True)
        consumer.write_text(self.consumer("2.0"), encoding="utf-8")
        previous_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, checker.run_staged(self.root / "pom.xml"))
        finally:
            os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
