import importlib.util
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


SCRIPTS = Path(__file__).parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "verify_bom_consumer_contract", SCRIPTS / "verify-bom-consumer-contract.py"
)
contract = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(contract)

drift = contract.drift

UNLAXER_COMMON = ("org.unlaxer", "unlaxer-common")
DOMA_CORE = ("org.seasar.doma", "doma-core")
BUILDING_HIERARCHY = ("org.unlaxer", "building-hierarchy")


def managed_dependency(group: str, artifact: str, version: str, comment: str | None) -> str:
    marker = f"\n        <!-- {comment} -->" if comment else ""
    return (
        "      <dependency>\n"
        f"        <groupId>{group}</groupId>\n"
        f"        <artifactId>{artifact}</artifactId>\n"
        f"        <version>{version}</version>{marker}\n"
        "      </dependency>\n"
    )


def bom_pom(dependencies: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.unlaxer</groupId><artifactId>unlaxer-bom</artifactId><version>2026.53</version>
  <packaging>pom</packaging>
  <properties><java.baseline>21</java.baseline></properties>
  <distributionManagement>
    <repository>
      <id>github-unlaxer</id>
      <url>https://maven.pkg.github.com/opaopa6969/unlaxer-bom</url>
    </repository>
  </distributionManagement>
  <dependencyManagement>
    <dependencies>
{dependencies}    </dependencies>
  </dependencyManagement>
</project>
"""


DEFAULT_BOM = bom_pom(
    managed_dependency("org.unlaxer", "unlaxer-common", "3.0.11", "bom registry: central")
    + managed_dependency("org.seasar.doma", "doma-core", "3.6.0", "bom registry: central")
    + managed_dependency("org.unlaxer", "building-hierarchy", "0.19.4", "bom registry: github")
)


class RegistryDeclarationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, text: str) -> Path:
        path = self.root / "pom.xml"
        path.write_text(text, encoding="utf-8")
        return path

    def classify(self, text: str):
        path = self.write(text)
        project = drift.parse_pom(path)
        return contract.classify_registries(
            drift.managed_versions(path), contract.registry_declarations(project)
        )

    def test_declarations_are_read_per_coordinate(self):
        project = drift.parse_pom(self.write(DEFAULT_BOM))
        self.assertEqual(
            {UNLAXER_COMMON: "central", DOMA_CORE: "central", BUILDING_HIERARCHY: "github"},
            contract.registry_declarations(project),
        )

    def test_coordinates_are_split_by_registry(self):
        buckets = self.classify(DEFAULT_BOM)
        self.assertEqual([DOMA_CORE, UNLAXER_COMMON], buckets["central"])
        self.assertEqual([BUILDING_HIERARCHY], buckets["github"])

    def test_undeclared_coordinate_is_fatal_and_named(self):
        text = bom_pom(
            managed_dependency("org.unlaxer", "unlaxer-common", "3.0.11", "bom registry: central")
            + managed_dependency("org.seasar.doma", "doma-core", "3.6.0", None)
        )
        with self.assertRaises(contract.ContractViolation) as raised:
            self.classify(text)
        self.assertIn("org.seasar.doma:doma-core", str(raised.exception))
        self.assertNotIn("org.unlaxer:unlaxer-common", str(raised.exception))

    def test_unknown_registry_value_is_fatal(self):
        text = bom_pom(
            managed_dependency("org.unlaxer", "unlaxer-common", "3.0.11", "bom registry: central")
            + managed_dependency("org.seasar.doma", "doma-core", "3.6.0", "bom registry: nexus")
        )
        with self.assertRaises(contract.ContractViolation) as raised:
            self.classify(text)
        self.assertIn("nexus", str(raised.exception))

    def test_bom_without_any_central_coordinate_is_fatal(self):
        text = bom_pom(
            managed_dependency("org.unlaxer", "building-hierarchy", "0.19.4", "bom registry: github")
        )
        with self.assertRaises(contract.ContractViolation) as raised:
            self.classify(text)
        self.assertIn("central", str(raised.exception))

    def test_registry_comment_does_not_act_as_drift_exception(self):
        """`bom registry:` を `bom 例外:` と取り違えると drift 検査に穴が空く。"""
        project = drift.parse_pom(self.write(DEFAULT_BOM))
        for dependency in drift.dependency_elements(project, managed=True):
            self.assertFalse(drift.has_reasoned_exception(dependency))

    def test_bom_exception_comment_still_works(self):
        text = bom_pom(
            managed_dependency(
                "org.unlaxer", "unlaxer-common", "3.0.11",
                "bom 例外: unlaxer-bom #123 に入るまでの先行検証",
            )
        )
        project = drift.parse_pom(self.write(text))
        dependency = drift.dependency_elements(project, managed=True)[0]
        self.assertTrue(drift.has_reasoned_exception(dependency))
        self.assertEqual({}, contract.registry_declarations(project))


class ConsumerGenerationTest(unittest.TestCase):
    def parse(self, text: str) -> ET.Element:
        return ET.fromstring(text)

    def test_consumer_imports_bom_and_omits_versions(self):
        text = contract.consumer_pom(
            ("org.unlaxer", "unlaxer-bom", "2026.53"), [UNLAXER_COMMON, DOMA_CORE], None, 21
        )
        root = self.parse(text)
        management = [e for e in root if drift.local_name(e.tag) == "dependencyManagement"][0]
        imported = list(list(management)[0])[0]
        self.assertEqual("unlaxer-bom", drift.child_text(imported, "artifactId"))
        self.assertEqual("2026.53", drift.child_text(imported, "version"))
        self.assertEqual("pom", drift.child_text(imported, "type"))
        self.assertEqual("import", drift.child_text(imported, "scope"))

        declared = [e for e in root if drift.local_name(e.tag) == "dependencies"][0]
        self.assertEqual(2, len(list(declared)))
        for dependency in declared:
            self.assertIsNone(drift.child_text(dependency, "version"))

    def test_consumer_compiles_against_the_declared_baseline(self):
        text = contract.consumer_pom(("g", "a", "1"), [UNLAXER_COMMON], None, 17)
        self.assertIn("<maven.compiler.release>17</maven.compiler.release>", text)

    def test_consumer_excludes_coordinates_it_cannot_resolve(self):
        text = contract.consumer_pom(
            ("org.unlaxer", "unlaxer-bom", "2026.53"), [UNLAXER_COMMON], None, 21
        )
        self.assertNotIn("building-hierarchy", text)

    def test_consumer_adds_repository_only_when_requested(self):
        without = contract.consumer_pom(("g", "a", "1"), [UNLAXER_COMMON], None, 21)
        self.assertNotIn("<repositories>", without)
        with_repository = contract.consumer_pom(
            ("g", "a", "1"), [UNLAXER_COMMON], ("github-unlaxer", "https://example.invalid/m2"), 21
        )
        self.assertIn("https://example.invalid/m2", with_repository)

    def test_contract_source_touches_founding_incident_symbols(self):
        source = contract.contract_source([UNLAXER_COMMON, DOMA_CORE])
        self.assertIn("org.unlaxer.CodePointIndex.of(1)", source)
        self.assertIn("org.unlaxer.CodePointIndex.ZERO", source)
        self.assertIn("org.seasar.doma.Dao.class", source)

    def test_contract_source_drops_snippets_for_absent_coordinates(self):
        source = contract.contract_source([DOMA_CORE])
        self.assertNotIn("CodePointIndex", source)
        self.assertIn("org.seasar.doma.Dao.class", source)

    def test_settings_omit_servers_without_credentials(self):
        self.assertNotIn("<servers>", contract.settings_xml(None))

    def test_settings_never_embed_the_token_value(self):
        """トークンの実値をディスクに書かない。Maven の ${env.*} 補間に任せる。"""
        settings = contract.settings_xml("github-unlaxer")
        self.assertIn("<id>github-unlaxer</id>", settings)
        self.assertIn("${env.GH_PKG_TOKEN}", settings)
        self.assertIn("${env.GH_PKG_USER}", settings)


class InjectionCheckTest(unittest.TestCase):
    managed = {UNLAXER_COMMON: "3.0.11", BUILDING_HIERARCHY: "0.19.4"}

    def test_matching_effective_versions_pass(self):
        contract.check_injection(
            self.managed,
            {UNLAXER_COMMON: "3.0.11", BUILDING_HIERARCHY: "0.19.4"},
            {UNLAXER_COMMON: "3.0.11"},
            [UNLAXER_COMMON],
        )

    def test_effective_version_differing_from_pin_is_a_violation(self):
        with self.assertRaises(contract.ContractViolation) as raised:
            contract.check_injection(
                self.managed,
                {UNLAXER_COMMON: "3.0.11", BUILDING_HIERARCHY: "0.19.3"},
                {UNLAXER_COMMON: "3.0.11"},
                [UNLAXER_COMMON],
            )
        self.assertIn("effective=0.19.3", str(raised.exception))

    def test_missing_managed_coordinate_is_a_violation(self):
        with self.assertRaises(contract.ContractViolation) as raised:
            contract.check_injection(
                self.managed, {UNLAXER_COMMON: "3.0.11"}, {UNLAXER_COMMON: "3.0.11"}, [UNLAXER_COMMON]
            )
        self.assertIn("org.unlaxer:building-hierarchy", str(raised.exception))

    def test_version_not_injected_into_declared_dependency_is_a_violation(self):
        with self.assertRaises(contract.ContractViolation) as raised:
            contract.check_injection(
                self.managed,
                {UNLAXER_COMMON: "3.0.11", BUILDING_HIERARCHY: "0.19.4"},
                {},
                [UNLAXER_COMMON],
            )
        self.assertIn("effective dependencies に現れません", str(raised.exception))


class FailureClassificationTest(unittest.TestCase):
    def test_missing_artifact_is_a_contract_violation(self):
        error = contract.maven_failure(
            "resolve", "[ERROR] Could not find artifact org.unlaxer:unlaxer-common:jar:3.0.99 in central"
        )
        self.assertIsInstance(error, contract.ContractViolation)

    def test_compile_error_is_a_contract_violation(self):
        error = contract.maven_failure("compile", "[ERROR] cannot find symbol\n  symbol: method of(int)")
        self.assertIsInstance(error, contract.ContractViolation)

    def test_authentication_failure_names_authentication(self):
        error = contract.maven_failure(
            "resolve",
            "[ERROR] Could not transfer artifact ... status code: 401, reason phrase: Unauthorized (401)",
        )
        self.assertIsInstance(error, contract.Unrunnable)
        self.assertIn("認証", str(error))
        self.assertIn("read:packages", str(error))

    def test_network_failure_is_unrunnable(self):
        for output in (
            "[ERROR] Could not transfer artifact org.unlaxer:unlaxer-common:pom:3.0.11",
            "[ERROR] Cannot access central in offline mode",
            "[ERROR] java.net.UnknownHostException: repo.maven.apache.org",
        ):
            self.assertIsInstance(contract.maven_failure("resolve", output), contract.Unrunnable)


class EnvironmentTest(unittest.TestCase):
    def test_missing_maven_is_unrunnable(self):
        original = shutil.which
        shutil.which = lambda name: None
        try:
            with self.assertRaises(contract.Unrunnable):
                contract.maven_executable()
        finally:
            shutil.which = original

    def test_github_credentials_are_only_checked_for_presence(self):
        import os

        previous = {name: os.environ.pop(name, None) for name in ("GH_PKG_USER", "GH_PKG_TOKEN")}
        try:
            with self.assertRaises(contract.Unrunnable) as raised:
                contract.require_github_credentials()
            self.assertIn("GH_PKG_USER", str(raised.exception))
            self.assertIn("GH_PKG_TOKEN", str(raised.exception))
            os.environ["GH_PKG_USER"] = "someone"
            os.environ["GH_PKG_TOKEN"] = "secret-value"
            self.assertIsNone(contract.require_github_credentials())
        finally:
            for name, value in previous.items():
                os.environ.pop(name, None)
                if value is not None:
                    os.environ[name] = value


class ExitCodeTest(unittest.TestCase):
    """「壊れている」(1) と「確かめられなかった」(2) を混同しない。"""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def run_main(self, arguments: list[str]) -> int:
        import contextlib
        import io
        import sys

        previous = sys.argv
        sys.argv = ["verify-bom-consumer-contract.py", *arguments]
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                return contract.main()
        finally:
            sys.argv = previous

    def test_unresolvable_pin_property_is_a_contract_violation(self):
        path = self.root / "pom.xml"
        path.write_text(
            bom_pom(
                managed_dependency(
                    "org.unlaxer", "unlaxer-common", "${unlaxer-common.versoin}",
                    "bom registry: central",
                )
            ),
            encoding="utf-8",
        )
        self.assertEqual(1, self.run_main(["--bom", str(path)]))

    def test_unreadable_pom_is_a_contract_violation(self):
        path = self.root / "pom.xml"
        path.write_text("<project", encoding="utf-8")
        self.assertEqual(1, self.run_main(["--bom", str(path)]))

    def test_absent_bom_file_is_unrunnable(self):
        self.assertEqual(2, self.run_main(["--bom", str(self.root / "missing.xml")]))


class RenderTest(unittest.TestCase):
    managed = {UNLAXER_COMMON: "3.0.11", BUILDING_HIERARCHY: "0.19.4"}

    def test_unverified_coordinates_are_listed_not_skipped(self):
        output = contract.render(self.managed, {UNLAXER_COMMON}, 21, {UNLAXER_COMMON: 21})
        self.assertIn("org.unlaxer:building-hierarchy", output)
        self.assertIn("UNVERIFIED", output)

    def test_partial_run_never_claims_the_contract_holds(self):
        """exit 0 を「全部確かめた」と読ませない。"""
        output = contract.render(self.managed, {UNLAXER_COMMON}, 21, {UNLAXER_COMMON: 21})
        self.assertIn("部分検証", output)
        self.assertIn("pin が実在しなくてもこの実行では検出できない", output)
        self.assertNotIn("全座標検証", output)

    def test_full_run_says_so(self):
        output = contract.render(
            self.managed, set(self.managed), 21, {UNLAXER_COMMON: 21, BUILDING_HIERARCHY: 17}
        )
        self.assertIn("全座標検証", output)
        self.assertNotIn("部分検証", output)

    def test_limits_are_always_stated(self):
        output = contract.render(self.managed, set(self.managed), 21, {})
        self.assertIn("この検証が保証しないこと", output)

    def test_measured_java_release_is_reported(self):
        output = contract.render(self.managed, {UNLAXER_COMMON}, 21, {UNLAXER_COMMON: 21})
        self.assertIn("Java baseline: 宣言 21 / 検証した jar の実測最大 21", output)


class PinPresenceTest(unittest.TestCase):
    """version を失った managed dependency が全検査から黙って消えないこと。"""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def check(self, text: str):
        path = self.root / "pom.xml"
        path.write_text(text, encoding="utf-8")
        project = drift.parse_pom(path)
        try:
            managed = drift.managed_versions(path)
        except drift.PomError:
            managed = {}
        return contract.check_all_pins_present(project, managed)

    def test_managed_dependency_without_version_is_fatal(self):
        text = bom_pom(
            managed_dependency("org.unlaxer", "unlaxer-common", "3.0.11", "bom registry: central")
            + "      <dependency>\n"
            "        <groupId>org.unlaxer</groupId>\n"
            "        <artifactId>historical-town-names</artifactId>\n"
            "        <!-- bom registry: github -->\n"
            "      </dependency>\n"
        )
        with self.assertRaises(contract.ContractViolation) as raised:
            self.check(text)
        self.assertIn("org.unlaxer:historical-town-names", str(raised.exception))

    def test_all_pins_present_passes(self):
        self.assertIsNone(self.check(DEFAULT_BOM))


class JavaBaselineTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def project(self, properties: str) -> ET.Element:
        path = self.root / "pom.xml"
        text = bom_pom(
            managed_dependency("org.unlaxer", "unlaxer-common", "3.0.11", "bom registry: central")
        ).replace("<properties><java.baseline>21</java.baseline></properties>", properties, 1)
        path.write_text(text, encoding="utf-8")
        return drift.parse_pom(path)

    def test_declared_baseline_is_read(self):
        self.assertEqual(
            21, contract.java_baseline(self.project("<properties><java.baseline>21</java.baseline></properties>"))
        )

    def test_missing_baseline_is_fatal(self):
        with self.assertRaises(contract.ContractViolation) as raised:
            contract.java_baseline(self.project("<properties/>"))
        self.assertIn("java.baseline", str(raised.exception))

    def test_non_numeric_baseline_is_fatal(self):
        with self.assertRaises(contract.ContractViolation):
            contract.java_baseline(self.project("<properties><java.baseline>21+</java.baseline></properties>"))

    def make_jar(self, entries: dict[str, int]) -> Path:
        path = self.root / "sample.jar"
        with zipfile.ZipFile(path, "w") as archive:
            for name, major in entries.items():
                archive.writestr(name, b"\xca\xfe\xba\xbe\x00\x00" + struct.pack(">H", major) + b"rest")
        return path

    def test_required_release_is_read_from_bytecode(self):
        self.assertEqual(21, contract.required_java_release(self.make_jar({"A.class": 65})))

    def test_multi_release_entries_are_ignored(self):
        jar = self.make_jar({"A.class": 61, "META-INF/versions/21/A.class": 65})
        self.assertEqual(17, contract.required_java_release(jar))

    def test_jar_newer_than_baseline_is_a_violation(self):
        repository = self.root / "repo"
        jar = contract.artifact_jar(repository, UNLAXER_COMMON, "3.0.11")
        jar.parent.mkdir(parents=True)
        shutil.copy(self.make_jar({"A.class": 65}), jar)
        with self.assertRaises(contract.ContractViolation) as raised:
            contract.check_java_baseline(repository, {UNLAXER_COMMON: "3.0.11"}, [UNLAXER_COMMON], 17)
        self.assertIn("Java 21 が必要", str(raised.exception))
        self.assertIn("UnsupportedClassVersionError", str(raised.exception))

    def test_jar_within_baseline_passes(self):
        repository = self.root / "repo"
        jar = contract.artifact_jar(repository, UNLAXER_COMMON, "3.0.11")
        jar.parent.mkdir(parents=True)
        shutil.copy(self.make_jar({"A.class": 61}), jar)
        self.assertEqual(
            {UNLAXER_COMMON: 17},
            contract.check_java_baseline(repository, {UNLAXER_COMMON: "3.0.11"}, [UNLAXER_COMMON], 21),
        )


class RequireAllTest(unittest.TestCase):
    def test_unverified_coordinate_fails_require_all(self):
        with self.assertRaises(contract.ContractViolation) as raised:
            contract.check_all_verified(
                {UNLAXER_COMMON: "3.0.11", BUILDING_HIERARCHY: "0.19.4"}, [UNLAXER_COMMON]
            )
        self.assertIn("org.unlaxer:building-hierarchy", str(raised.exception))

    def test_fully_verified_passes_require_all(self):
        self.assertIsNone(
            contract.check_all_verified({UNLAXER_COMMON: "3.0.11"}, [UNLAXER_COMMON])
        )


if __name__ == "__main__":
    unittest.main()
