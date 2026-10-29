import importlib.util
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1] / 'scripts/publish-source-packages.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

POM = '''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>org.unlaxer</groupId><artifactId>municipality-history</artifactId><version>99.0.0</version>
<properties><maven.compiler.release>21</maven.compiler.release><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties>
<build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.13.0</version></plugin><plugin><groupId>org.sonatype.central</groupId><artifactId>central-publishing-maven-plugin</artifactId><version>0.7.0</version><extensions>true</extensions></plugin></plugins></build>
</project>'''
ENV = {'MAVEN_PACKAGES_READ_USER': 'caulis-deployuser', 'MAVEN_PACKAGES_READ_TOKEN': 'read',
       'MAVEN_PACKAGES_WRITE_USER': 'writer', 'MAVEN_PACKAGES_WRITE_TOKEN': 'write'}


class SourcePublisherTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.pom = self.root / 'pom.xml'
        self.pom.write_text(POM)
        self.items = publisher.projects(self.root, 'municipality-history')

    def test_registry_presence_uses_head_without_reading_or_redirecting(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.side_effect = AssertionError('Presence must not download the artifact')
        with patch.object(publisher.urllib.request, 'build_opener', return_value=opener) as build:
            self.assertTrue(publisher.request('https://maven.pkg.github.com/caulis/unlaxer-bom/file.jar',
                                              'read-token', 'caulis-deployuser', presence=True))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'HEAD')
        self.assertIs(build.call_args.args[0], publisher.NoRedirect)
        self.assertIn('Authorization', request.unredirected_hdrs)
        self.assertNotIn('Authorization', request.headers)
        response.read.assert_not_called()

    def test_identity_request_still_reads_json_with_get(self):
        opener = MagicMock()
        opener.open.return_value = io.BytesIO(b'{"login":"caulis-deployuser"}')
        with patch.object(publisher.urllib.request, 'build_opener', return_value=opener):
            result = publisher.request('https://api.github.com/user', 'read-token')
        self.assertEqual(result['login'], 'caulis-deployuser')
        self.assertEqual(opener.open.call_args.args[0].get_method(), 'GET')

    def test_head_treats_only_404_as_absent_and_rejects_auth_errors_and_redirects(self):
        for status in [404, 401, 403, 302]:
            opener = MagicMock()
            opener.open.side_effect = urllib.error.HTTPError('https://maven.pkg.github.com/file', status,
                                                             'test response', {}, None)
            with patch.object(publisher.urllib.request, 'build_opener', return_value=opener):
                if status == 404:
                    self.assertFalse(publisher.request('https://maven.pkg.github.com/file', 'token', 'reader', presence=True))
                else:
                    with self.assertRaises(publisher.PublishError):
                        publisher.request('https://maven.pkg.github.com/file', 'token', 'reader', presence=True)

    def test_same_owner_pinned_source_and_managed_identity(self):
        name = publisher.validate_inputs('caulis/unlaxer-bom', 'caulis/municipality-history', 'a' * 40, ENV,
                                         fetch=lambda *args: {'login': 'caulis-deployuser'})
        self.assertEqual(name, 'municipality-history')
        for repository, source, sha in [('caulis/other', 'caulis/municipality-history', 'a' * 40),
                                       ('caulis/unlaxer-bom', 'opaopa6969/municipality-history', 'a' * 40),
                                       ('caulis/unlaxer-bom', 'caulis/unknown', 'a' * 40),
                                       ('caulis/unlaxer-bom', 'caulis/municipality-history', 'main')]:
            with self.assertRaises(publisher.PublishError):
                publisher.validate_inputs(repository, source, sha, ENV, fetch=lambda *a: self.fail('network before validation'))

    def test_wrong_account_or_missing_secret_does_not_fall_back(self):
        for env, login in [(ENV, 'opaopa6969'), ({**ENV, 'MAVEN_PACKAGES_READ_TOKEN': ''}, 'caulis-deployuser'),
                           ({**ENV, 'MAVEN_PACKAGES_READ_USER': 'opaopa6969'}, 'opaopa6969')]:
            with self.assertRaises(publisher.PublishError):
                publisher.validate_inputs('caulis/unlaxer-bom', 'caulis/unlaxer-bom', 'a' * 40, env,
                                          fetch=lambda *a: {'login': login})

    def test_source_coordinates_cannot_be_changed_or_inherited(self):
        for text in [POM.replace('municipality-history', 'other'), POM.replace('99.0.0', '${revision}')]:
            self.pom.write_text(text)
            with self.assertRaises(publisher.PublishError):
                publisher.projects(self.root, 'municipality-history')

    def test_existing_release_is_skipped_and_partial_release_rejected(self):
        selected, existing = publisher.select_missing(self.items, 'caulis/unlaxer-bom', ENV, False, fetch=lambda *a, **k: True)
        self.assertEqual(selected, [])
        self.assertEqual(existing, self.items)
        with self.assertRaises(publisher.PublishError):
            publisher.select_missing(self.items, 'caulis/unlaxer-bom', ENV, False,
                                     fetch=lambda url, *a, **k: url.endswith('.pom'))
        with self.assertRaises(publisher.PublishError):
            def forbidden(*args, **kwargs):raise publisher.PublishError('HTTP 403')
            publisher.select_missing(self.items, 'caulis/unlaxer-bom', ENV, False, fetch=forbidden)

    def test_snapshot_and_dry_run_build_without_release_lookup(self):
        def no_request(*args, **kwargs):self.fail('unexpected lookup')
        snapshot = [{**self.items[0], 'version': '1.0-SNAPSHOT'}]
        self.assertEqual(publisher.select_missing(snapshot, 'caulis/unlaxer-bom', ENV, False, fetch=no_request), (snapshot, []))
        self.assertEqual(publisher.select_missing(self.items, 'caulis/unlaxer-bom', ENV, True, fetch=no_request), (self.items, []))

    def test_all_builds_pass_before_any_remote_publish(self):
        calls = []
        def run(command, **kwargs):calls.append(command)
        items = self.items + [{**self.items[0], 'pom': 'sibling/pom.xml'}]
        publisher.build_and_publish(self.root, items, self.root/'settings.xml', self.root/'m2', self.root/'staging', False, run)
        self.assertEqual(len(calls), 4)
        self.assertTrue(all('clean' in c and any('file://' in a for a in c) for c in calls[:2]))
        self.assertTrue(all('-DskipTests' in c and not any('file://' in a for a in c) for c in calls[2:]))

    def test_failed_build_never_publishes_remotely(self):
        calls = []
        def fail_second(command, **kwargs):
            calls.append(command)
            if len(calls)==2:raise subprocess.CalledProcessError(1, command)
        with self.assertRaises(subprocess.CalledProcessError):
            publisher.build_and_publish(self.root, self.items*2, self.root/'settings.xml', self.root/'m2', self.root/'staging', False, fail_second)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(any('file://' in a for a in c) for c in calls))

    def test_configuration_preserves_gav_and_uses_env_credentials(self):
        settings = self.root/'settings.xml'
        publisher.configuration.configure([self.pom], 'caulis/unlaxer-bom', settings, ENV)
        pom = ET.parse(self.pom)
        self.assertEqual(pom.findtext('{*}version'), '99.0.0')
        plugins = [n.text for n in pom.findall('.//{*}plugin/{*}artifactId')]
        self.assertNotIn('central-publishing-maven-plugin', plugins)
        self.assertIn('maven-compiler-plugin', plugins)
        self.assertEqual(pom.findtext('{*}distributionManagement/{*}repository/{*}url'), 'https://maven.pkg.github.com/caulis/unlaxer-bom')
        self.assertIn('${env.MAVEN_PACKAGES_WRITE_TOKEN}', settings.read_text())
        self.assertEqual(settings.stat().st_mode & 0o777, 0o600)

    def bundled_fixture(self):
        self.pom.write_text(POM.replace('</project>', '<dependencies><dependency>'
            '<groupId>org.unlaxer</groupId><artifactId>municipality-history</artifactId>'
            '<version>1.0.0</version></dependency></dependencies></project>'))
        checksums = {}
        for relative in publisher.JAPANPOST_BUNDLED_DEPENDENCY:
            path = self.root / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(relative.encode())
            checksums[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return checksums

    def test_bundled_legacy_dependency_is_installed_only_in_isolated_cache(self):
        checksums = self.bundled_fixture()
        calls = []
        with patch.object(publisher, 'JAPANPOST_BUNDLED_DEPENDENCY', checksums):
            files = publisher.install_bundled_dependency(self.root, 'japanpost-history', self.items,
                self.root/'settings.xml', self.root/'isolated', lambda command, **kwargs: calls.append(command))
        self.assertEqual({file['path']: file['sha256'] for file in files}, checksums)
        self.assertEqual(len(calls), 1)
        self.assertIn('-Dmaven.repo.local=' + str(self.root/'isolated'), calls[0])
        self.assertIn('org.apache.maven.plugins:maven-install-plugin:3.1.4:install-file', calls[0])
        self.assertNotIn('deploy', ' '.join(calls[0]))
        self.assertNotIn('central-publishing', (self.root/'dependency-install.xml').read_text())

    def test_bundled_dependency_is_not_used_for_current_version_or_skipped_release(self):
        self.bundled_fixture()
        def no_run(*args, **kwargs):self.fail('unexpected dependency installation')
        for name, items in [('japanpost-history', []), ('municipality-history', self.items)]:
            self.assertEqual(publisher.install_bundled_dependency(self.root, name, items,
                self.root/'settings.xml', self.root/'isolated', no_run), [])
        self.pom.write_text(self.pom.read_text().replace('<version>1.0.0</version>', '<version>1.0.2</version>'))
        self.assertEqual(publisher.install_bundled_dependency(self.root, 'japanpost-history', self.items,
            self.root/'settings.xml', self.root/'isolated', no_run), [])

    def test_missing_changed_or_external_bundle_fails_before_maven(self):
        checksums = self.bundled_fixture()
        jar = self.root/'local-repo/municipality-history-1.0.0.jar'
        original = jar.read_bytes()
        for kind in ['changed', 'missing', 'external']:
            if jar.exists() or jar.is_symlink():jar.unlink()
            if kind == 'changed':jar.write_bytes(b'wrong binary')
            if kind == 'external':jar.symlink_to('/dev/null')
            with patch.object(publisher, 'JAPANPOST_BUNDLED_DEPENDENCY', checksums):
                with self.assertRaises(publisher.PublishError):
                    publisher.install_bundled_dependency(self.root, 'japanpost-history', self.items,
                        self.root/'settings.xml', self.root/'isolated', lambda *a, **k: self.fail('Maven before validation'))
        jar.unlink()
        jar.write_bytes(original)

    def test_central_extension_is_removed_from_profiles_as_well(self):
        central = '<plugin><groupId>org.sonatype.central</groupId><artifactId>central-publishing-maven-plugin</artifactId><version>0.7.0</version><extensions>true</extensions></plugin>'
        self.pom.write_text(POM.replace('</project>', '<profiles><profile><id>central</id><activation><activeByDefault>true</activeByDefault></activation><build><plugins>' + central + '</plugins></build></profile></profiles></project>'))
        publisher.configuration.configure([self.pom], 'caulis/unlaxer-bom', self.root/'settings.xml', ENV)
        self.assertNotIn('central-publishing-maven-plugin', self.pom.read_text())
        self.assertEqual(ET.parse(self.pom).findtext('{*}version'), '99.0.0')

    @unittest.skipUnless(os.environ.get('SOURCE_PUBLISH_MAVEN_TEST') == 'true', 'explicit Maven integration test')
    def test_real_maven_dry_run_deploys_only_into_file_registry(self):
        settings, staging = self.root/'settings.xml', self.root/'staging'
        publisher.configuration.configure([self.pom], 'caulis/unlaxer-bom', settings, ENV)
        # Check before Maven starts so a regression cannot contact Central.
        self.assertNotIn('central-publishing-maven-plugin', self.pom.read_text())
        publisher.build_and_publish(self.root, self.items, settings, self.root/'m2', staging, True)
        package = staging/'org/unlaxer/municipality-history/99.0.0'
        self.assertTrue((package/'municipality-history-99.0.0.jar').is_file())
        self.assertTrue((package/'municipality-history-99.0.0.pom').is_file())
        self.assertTrue(publisher.staged_files(staging))


if __name__ == '__main__':
    unittest.main()
