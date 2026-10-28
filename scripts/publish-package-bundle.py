#!/usr/bin/env python3
"""Validate and publish an immutable Maven migration bundle to this repository."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


class PublishError(Exception):
    pass


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def validate_bundle(path, checksum, repository, directory):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository):
        raise PublishError("Invalid repository")
    if not re.fullmatch(r"[a-f0-9]{64}", checksum) or digest(path) != checksum:
        raise PublishError("Bundle SHA-256 mismatch")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise PublishError("Duplicate archive entry")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schemaVersion") != 1 or manifest.get("targetRepository") != repository:
            raise PublishError("Bundle target repository or schema mismatch")
        artifacts = manifest["artifacts"]
        if not artifacts:
            raise PublishError("Empty bundle")
        expected = {"manifest.json"}
        coordinates = set()
        for artifact in artifacts:
            group, name, version = (artifact[k] for k in ("groupId", "artifactId", "version"))
            if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", group):
                raise PublishError("Invalid groupId")
            if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) for value in (name, version)):
                raise PublishError("Invalid artifactId or version")
            if version.endswith("-SNAPSHOT"):
                raise PublishError("SNAPSHOT cannot be bootstrapped")
            relative = f"{group.replace('.', '/')}/{name}/{version}/{name}-{version}"
            if relative in coordinates:
                raise PublishError("Duplicate artifact coordinate")
            coordinates.add(relative)
            packaging = artifact["packaging"]
            if packaging not in ("pom", "jar"):
                raise PublishError("Unsupported packaging")
            kinds = set()
            for file in artifact["files"]:
                extension, classifier = file["extension"], file["classifier"]
                kind = (extension, classifier)
                if kind not in {("pom", ""), ("jar", ""), ("jar", "sources"), ("jar", "javadoc")} or kind in kinds:
                    raise PublishError("Invalid or repeated artifact file")
                kinds.add(kind)
                suffix = ("-" + classifier if classifier else "") + "." + extension
                name_in_zip = "artifacts/" + relative + suffix
                if file["path"] != name_in_zip:
                    raise PublishError("Artifact path does not match coordinate")
                expected.add(name_in_zip)
                destination = directory / name_in_zip
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name_in_zip) as source, destination.open("wb") as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
                if destination.stat().st_size != file["size"] or digest(destination) != file["sha256"]:
                    raise PublishError("Artifact checksum or size mismatch: " + name_in_zip)
                if extension == "pom":
                    original = "originals/" + relative + ".pom"
                    if file.get("sourcePath") != original:
                        raise PublishError("Invalid original POM path")
                    expected.add(original)
                    if hashlib.sha256(archive.read(original)).hexdigest() != file["sourceSha256"]:
                        raise PublishError("Original POM checksum mismatch")
                    check_pom(destination, artifact, repository)
                elif file["sourceSha256"] != file["sha256"]:
                    raise PublishError("Jar must be identical to its source")
            required = {("pom", "")} | ({("jar", "")} if packaging == "jar" else set())
            if not required <= kinds or (packaging == "pom" and kinds != required):
                raise PublishError("Missing or unexpected main artifact")
        if expected != set(names):
            raise PublishError("Unexpected or missing archive entries")
    return manifest


def check_pom(path, artifact, repository):
    project = ET.parse(path).getroot()
    if project.tag != "{http://maven.apache.org/POM/4.0.0}project":
        raise PublishError("Invalid POM")
    for key in ("groupId", "artifactId", "version"):
        value = project.findtext("{*}" + key)
        if value is None and key != "artifactId":
            value = project.findtext("{*}parent/{*}" + key)
        if value != artifact[key]:
            raise PublishError("POM coordinate mismatch")
    if project.findtext("{*}packaging", "jar") != artifact["packaging"]:
        raise PublishError("POM packaging mismatch")
    prefix = "https://maven.pkg.github.com/"
    owner = repository.split("/")[0]
    for element in project.iter():
        if element.text and element.text.strip().startswith(prefix):
            if not element.text.strip().startswith(prefix + owner + "/"):
                raise PublishError("POM references a different Packages owner")
    for element in project.findall("{*}distributionManagement/{*}repository/{*}url"):
        if element.text != prefix + repository:
            raise PublishError("POM distribution repository mismatch")


def remote_digest(repository, file, directory):
    # Authentication stays in stdin, and curl strips it on cross-host redirects.
    token, user = (os.environ.get(k, "") for k in ("GITHUB_TOKEN", "GITHUB_ACTOR"))
    if not token or not user or any(c in token + user for c in '\r\n"\\'):
        raise PublishError("GITHUB_TOKEN and GITHUB_ACTOR are required")
    url = "https://maven.pkg.github.com/" + repository + "/" + file["path"].removeprefix("artifacts/")
    destination = directory / "remote-file"
    result = subprocess.run(
        ["curl", "--disable", "--config", "-", "--silent", "--show-error", "--location",
         "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "5",
         "--connect-timeout", "15", "--max-time", "300", "--retry", "2",
         "--output", str(destination), "--write-out", "%{http_code}", url],
        input=f'user = "{user}:{token}"\n', text=True, capture_output=True)
    status = result.stdout.strip()
    if result.returncode == 0 and status == "200":
        return digest(destination)
    if result.returncode == 0 and status == "404":
        return None
    raise PublishError(f"Registry read failed: HTTP {status or 'unknown'}, curl {result.returncode}")


def publication_plan(manifest, directory, probe=remote_digest):
    pending = []
    for artifact in manifest["artifacts"]:
        existing = []
        for file in artifact["files"]:
            actual = probe(manifest["targetRepository"], file, directory)
            if actual is not None and actual != file["sha256"]:
                raise PublishError("Existing artifact differs: " + file["path"])
            existing.append(actual is not None)
        if any(existing) and not all(existing):
            raise PublishError("Partially published coordinate; inspect before retry: " + artifact["artifactId"] + ":" + artifact["version"])
        if not any(existing):
            pending.append(artifact)
    return pending


def deploy(artifact, repository, directory):
    work = directory / "maven"
    work.mkdir(exist_ok=True)
    settings = work / "settings.xml"
    settings.write_text('''<settings><servers><server><id>migration-target</id>
<username>${env.GITHUB_ACTOR}</username><password>${env.GITHUB_TOKEN}</password>
</server></servers></settings>''')
    pom = next(file for file in artifact["files"] if file["extension"] == "pom")
    main = next(file for file in artifact["files"] if file["extension"] == artifact["packaging"] and not file["classifier"])
    command = ["mvn", "-B", "-ntp", "-s", str(settings),
               "org.apache.maven.plugins:maven-deploy-plugin:3.1.4:deploy-file",
               "-DrepositoryId=migration-target", "-Durl=https://maven.pkg.github.com/" + repository,
               "-DgeneratePom=false", "-DpomFile=" + str(directory / pom["path"]),
               "-Dfile=" + str(directory / main["path"]), "-Dpackaging=" + artifact["packaging"]]
    command += ["-D" + key + "=" + artifact[key] for key in ("groupId", "artifactId", "version")]
    for file in artifact["files"]:
        if file["classifier"]:
            command.append("-D" + file["classifier"] + "=" + str(directory / file["path"]))
    # Empty cwd prevents the source project's extensions/lifecycle from running.
    subprocess.run(command, cwd=work, check=True)


def publish(manifest, directory, execute=False, probe=remote_digest, deployer=deploy):
    pending = publication_plan(manifest, directory, probe)
    print(f"Preflight passed: {len(pending)} new, {len(manifest['artifacts']) - len(pending)} identical existing coordinates", flush=True)
    if execute:
        for artifact in pending:
            deployer(artifact, manifest["targetRepository"], directory)
            for file in artifact["files"]:
                if probe(manifest["targetRepository"], file, directory) != file["sha256"]:
                    raise PublishError("Published artifact verification failed: " + file["path"])
        print("Published and verified all coordinates", flush=True)
    else:
        print("Dry run; no registry writes", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="package-bootstrap-") as temporary:
            directory = Path(temporary)
            manifest = validate_bundle(args.bundle, args.sha256, args.repository, directory)
            publish(manifest, directory, args.publish)
    except (PublishError, OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
