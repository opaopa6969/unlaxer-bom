import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location(
    "publish_config", Path(__file__).parents[1] / "scripts/configure-maven-publish.py")
config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config)


class MavenPublishConfigTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pom = self.root / "pom.xml"
        self.settings = self.root / "settings.xml"
        self.content = '''<project xmlns="http://maven.apache.org/POM/4.0.0">
<modelVersion>4.0.0</modelVersion><groupId>org.example</groupId><artifactId>example</artifactId><version>1.2.3</version>
<!-- preserve source provenance -->
<scm><url>https://github.com/opaopa6969/example</url></scm>
<repositories><repository><id>github-unlaxer-bom</id><url>https://maven.pkg.github.com/opaopa6969/unlaxer-bom</url></repository></repositories>
<distributionManagement><repository><id>github-unlaxer-bom</id><url>https://maven.pkg.github.com/opaopa6969/example</url></repository></distributionManagement>
<properties><maven.deploy.skip>true</maven.deploy.skip></properties>
</project>'''
        self.pom.write_text(self.content)
        self.env = {"MAVEN_PACKAGES_READ_USER": "read-user", "MAVEN_PACKAGES_READ_TOKEN": "read-secret",
                    "MAVEN_PACKAGES_WRITE_USER": "write-user", "MAVEN_PACKAGES_WRITE_TOKEN": "write-secret"}

    def configure(self):
        return config.configure([self.pom], "caulis/example", self.settings, self.env)

    def test_separates_read_and_write_credentials(self):
        self.assertEqual(self.configure(), {"github-unlaxer-bom"})
        pom = ET.parse(self.pom).getroot()
        self.assertEqual(pom.findtext("{*}repositories/{*}repository/{*}url"), "https://maven.pkg.github.com/caulis/unlaxer-bom")
        self.assertEqual(pom.findtext("{*}distributionManagement/{*}repository/{*}id"), "github-local-publish")
        servers = {s.findtext("id"): s.findtext("password") for s in ET.parse(self.settings).findall("servers/server")}
        self.assertEqual(servers, {"github-unlaxer-bom": "${env.MAVEN_PACKAGES_READ_TOKEN}", "github-local-publish": "${env.MAVEN_PACKAGES_WRITE_TOKEN}"})
        self.assertNotIn("read-secret", self.settings.read_text())
        self.assertNotIn("write-secret", self.settings.read_text())
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)

    def test_missing_private_read_token_leaves_input_untouched(self):
        del self.env["MAVEN_PACKAGES_READ_TOKEN"]
        with self.assertRaisesRegex(config.ConfigurationError, "MAVEN_PACKAGES_READ_TOKEN is required"):
            self.configure()
        self.assertEqual(self.pom.read_text(), self.content)
        self.assertFalse(self.settings.exists())

    def test_public_dependencies_need_no_read_pat(self):
        tree = ET.fromstring(self.content)
        tree.remove(tree.find("{*}repositories"))
        self.pom.write_bytes(ET.tostring(tree))
        del self.env["MAVEN_PACKAGES_READ_TOKEN"]
        del self.env["MAVEN_PACKAGES_READ_USER"]
        self.assertEqual(self.configure(), set())

    def test_preserves_version_source_links_and_deploy_skip(self):
        self.configure()
        pom = ET.parse(self.pom).getroot()
        self.assertEqual(pom.findtext("{*}version"), "1.2.3")
        self.assertEqual(pom.findtext("{*}properties/{*}maven.deploy.skip"), "true")
        self.assertEqual(pom.findtext("{*}scm/{*}url"), "https://github.com/opaopa6969/example")
        self.assertIn("preserve source provenance", self.pom.read_text())

    def test_configures_profiles_and_snapshot_repository(self):
        self.pom.write_text(self.content.replace('</project>', '''<profiles><profile><id>extra</id>
<pluginRepositories><pluginRepository><id>github-plugins</id><url>https://maven.pkg.github.com/opaopa6969/plugins</url></pluginRepository></pluginRepositories>
</profile></profiles></project>''').replace('</distributionManagement>', '<snapshotRepository><id>old</id><url>https://maven.pkg.github.com/opaopa6969/example</url></snapshotRepository></distributionManagement>'))
        self.assertEqual(self.configure(), {"github-unlaxer-bom", "github-plugins"})
        pom = ET.parse(self.pom).getroot()
        self.assertEqual(pom.findtext("{*}distributionManagement/{*}snapshotRepository/{*}url"), "https://maven.pkg.github.com/caulis/example")
        self.assertNotIn("maven.pkg.github.com/opaopa6969", self.pom.read_text())

    def test_invalid_target_rejected(self):
        with self.assertRaises(config.ConfigurationError):
            config.configure([self.pom], "caulis/../../other", self.settings, self.env)

    def test_repeated_configuration_does_not_duplicate_publish_plugin(self):
        self.configure()
        self.configure()
        plugins = ET.parse(self.pom).findall("{*}build/{*}plugins/{*}plugin")
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0].findtext("{*}version"), "3.1.4")


if __name__ == "__main__":
    unittest.main()
