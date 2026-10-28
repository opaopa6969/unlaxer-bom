#!/usr/bin/env python3
"""Build pinned source in isolation and publish into this owner's BOM registry."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('publish_config', Path(__file__).with_name('configure-maven-publish.py'))
configuration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configuration)

SOURCES = {
    'unlaxer-bom': [('pom.xml', 'org.unlaxer', 'unlaxer-bom')],
    'japanese-parser-common': [('pom.xml', 'org.unlaxer', 'japanese-parser-common')],
    'building-hierarchy': [('pom.xml', 'org.unlaxer', 'building-hierarchy')],
    'municipality-history': [('pom.xml', 'org.unlaxer', 'municipality-history')],
    'historical-town-names': [('pom.xml', 'org.unlaxer', 'historical-town-names')],
    'japanpost-history': [('pom.xml', 'org.unlaxer', 'japanpost-history')],
    'onigiri-parser': [('pom.xml', 'org.unlaxer', 'onigiri-parser')],
    'ABRUtils': [('pom.xml', 'org.unlaxer.geo', 'abr-utils'),
                 ('abr-api/pom.xml', 'org.unlaxer.geo', 'abr-api'),
                 ('abr-historical/pom.xml', 'org.unlaxer.geo', 'abr-historical')],
    'kugiri': [('pom.xml', 'org.unlaxer', 'kugiri'),
              ('building/pom.xml', 'org.unlaxer', 'kugiri-building')],
}


class PublishError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(url, token, user=None, presence=False):
    auth = ('Basic ' + base64.b64encode((user + ':' + token).encode()).decode()
            if user else 'Bearer ' + token)
    req = urllib.request.Request(url, headers={'User-Agent': 'unlaxer-source-publisher'})
    req.add_unredirected_header('Authorization', auth)
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
            return True if presence else json.load(response)
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        if code == 404 and presence:
            return False
        raise PublishError('Source/registry request returned HTTP ' + str(code)) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise PublishError('Source/registry request failed') from None


def validate_inputs(repository, source_repository, commit, environment, fetch=request):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*/unlaxer-bom', repository):
        raise PublishError('Target must be this owner\'s unlaxer-bom repository')
    owner = repository.split('/')[0]
    name = source_repository.partition('/')[2]
    if source_repository != owner + '/' + name or name not in SOURCES:
        raise PublishError('Source must be an allowed repository of the same owner')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise PublishError('An exact 40-character source commit SHA is required')
    for key in ('MAVEN_PACKAGES_READ_USER', 'MAVEN_PACKAGES_READ_TOKEN',
                'MAVEN_PACKAGES_WRITE_USER', 'MAVEN_PACKAGES_WRITE_TOKEN'):
        if not environment.get(key):
            raise PublishError('Selected Packages credentials are unavailable: ' + key)
    user = environment['MAVEN_PACKAGES_READ_USER']
    actual = fetch('https://api.github.com/user', environment['MAVEN_PACKAGES_READ_TOKEN']).get('login')
    if actual != user or (owner == 'caulis' and user != 'caulis-deployuser'):
        raise PublishError('Selected read token does not belong to the expected managed account')
    return name


def projects(root, name):
    result = []
    for relative, group, artifact in SOURCES[name]:
        path = root / relative
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise PublishError('Missing or external source POM: ' + relative)
        pom = ET.parse(path).getroot()
        version = pom.findtext('{*}version', '')
        if (pom.findtext('{*}groupId'), pom.findtext('{*}artifactId')) != (group, artifact):
            raise PublishError('Unexpected source coordinates: ' + relative)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version):
            raise PublishError('Source version must be explicit and unmodified')
        packaging = pom.findtext('{*}packaging', 'jar')
        if packaging not in ('pom', 'jar'):
            raise PublishError('Unsupported source packaging')
        result.append({'pom': relative, 'groupId': group, 'artifactId': artifact,
                       'version': version, 'packaging': packaging})
    return result


def select_missing(items, repository, environment, dry_run, fetch=request):
    if dry_run:
        return list(items), []
    selected, existing = [], []
    for item in items:
        if item['version'].endswith('-SNAPSHOT'):
            selected.append(item)
            continue
        base = ('https://maven.pkg.github.com/' + repository + '/' + item['groupId'].replace('.', '/')
                + '/' + item['artifactId'] + '/' + item['version'] + '/' + item['artifactId'] + '-' + item['version'])
        extensions = ['pom'] if item['packaging'] == 'pom' else ['pom', 'jar']
        present = [fetch(base + '.' + extension, environment['MAVEN_PACKAGES_READ_TOKEN'],
                         environment['MAVEN_PACKAGES_READ_USER'], presence=True) for extension in extensions]
        if all(present):
            existing.append(item)
        elif any(present):
            raise PublishError('Partially published release; inspect before retrying: ' + item['artifactId'] + ':' + item['version'])
        else:
            selected.append(item)
    return selected, existing


def build_and_publish(root, items, settings, local_repository, staging, dry_run, run=subprocess.run):
    base = ['mvn', '-B', '-ntp', '-N', '-s', str(settings),
            '-Dmaven.repo.local=' + str(local_repository), '-Dgpg.skip=true']
    # First complete tests and file-registry deployment for every selected module.
    # No remote publication happens if any build or test fails.
    for item in items:
        run(base + ['-f', str(root / item['pom']), 'clean', 'deploy',
                    '-DaltDeploymentRepository=' + configuration.PUBLISH_ID + '::' + staging.as_uri()], check=True)
    if not dry_run:
        for item in items:
            run(base + ['-f', str(root / item['pom']), 'deploy', '-DskipTests'], check=True)


def staged_files(staging):
    result = []
    for path in sorted(staging.rglob('*')):
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            result.append({'path': str(path.relative_to(staging)), 'sha256': digest.hexdigest()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--source-repository', required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        name = validate_inputs(args.repository, args.source_repository, args.source_commit, os.environ)
        root, work = args.source_root.resolve(), args.work.resolve()
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        if actual != args.source_commit:
            raise PublishError('Source checkout does not match the requested commit')
        if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root):
            raise PublishError('Source checkout must be unmodified')
        if work.exists() and any(work.iterdir()):
            raise PublishError('Use an empty work directory for every run')
        work.mkdir(parents=True, exist_ok=True)
        items = projects(root, name)
        selected, existing = select_missing(items, args.repository, os.environ, args.dry_run)
        settings, staging = work / 'settings.xml', work / 'staging'
        configuration.configure([root / item['pom'] for item in items], args.repository, settings, os.environ)
        staging.mkdir()
        build_and_publish(root, selected, settings, work / 'repository', staging, args.dry_run)
        report = {'sourceRepository': args.source_repository, 'sourceCommit': actual,
                  'targetRepository': args.repository, 'dryRun': args.dry_run,
                  'built': selected, 'existingReleaseSkipped': existing,
                  'stagedFiles': staged_files(staging)}
        (work / 'source-publish-report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Source publication complete: built=' + str(len(selected)) + ', existing=' + str(len(existing)))
    except (PublishError, configuration.ConfigurationError, OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(str(error) if isinstance(error, (PublishError, configuration.ConfigurationError)) else 'Source publication failed; inspect the build log', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
