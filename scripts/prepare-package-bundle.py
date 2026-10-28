#!/usr/bin/env python3
"""Prepare checksummed Maven migration inputs from existing published artifacts."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

SOURCES = {
    "central": "https://repo.maven.apache.org/maven2",
    **{name: "https://maven.pkg.github.com/opaopa6969/" + name for name in (
        "unlaxer-bom", "ABRUtils", "ikura-jaddress-parser", "shake-jaddress-parser",
        "okaka-jaddress-parser", "kombu-jaddress-parser")},
}
MAVEN_NS = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", MAVEN_NS)


class BundleError(Exception):
    pass


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_coordinate(coordinate):
    group, artifact, version = (coordinate[k] for k in ("groupId", "artifactId", "version"))
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", group):
        raise BundleError("Invalid groupId")
    for value in (artifact, version):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
            raise BundleError("Invalid artifactId or version")
    if version.endswith("-SNAPSHOT"):
        raise BundleError("Only immutable release versions may be migrated")
    if coordinate["source"] not in SOURCES:
        raise BundleError("Unknown source registry")
    return f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}"


def target_repository(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise BundleError("Invalid target repository")
    return value


def download(url, destination, optional=False):
    destination.parent.mkdir(parents=True, exist_ok=True)
    # curl drops HTTP authentication on cross-host redirects unless explicitly
    # told otherwise. Do not use --location-trusted: Packages redirects to blobs.
    config = ""
    token = ""
    if urllib.parse.urlsplit(url).hostname == "maven.pkg.github.com":
        token = os.environ.get("GITHUB_PACKAGES_TOKEN", "")
        if not token:
            raise BundleError("GITHUB_PACKAGES_TOKEN is required for the source registry")
        if any(char in token for char in '\r\n"\\'):
            raise BundleError("Invalid token format")
        config = 'user = "opaopa6969:' + token + '"\n'
    result = subprocess.run(
        ["curl", "--disable", "--config", "-", "--silent", "--show-error", "--location",
         "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "5",
         "--connect-timeout", "15", "--max-time", "300", "--retry", "2",
         "--output", str(destination), "--write-out", "%{http_code}", url],
        input=config, text=True, capture_output=True,
    )
    status = result.stdout.strip()
    if result.returncode == 0 and status == "200":
        return True
    destination.unlink(missing_ok=True)
    if result.returncode == 0 and status == "404" and optional:
        return False
    # Neither curl configuration nor server error bodies are diagnostic output.
    raise BundleError(f"Download failed: {url} (HTTP {status or 'unknown'}, curl {result.returncode})")


def migrate_pom(source, destination, coordinate, target):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(source, parser=parser)
    project = tree.getroot()
    if project.tag != "{" + MAVEN_NS + "}project":
        raise BundleError("Input is not a Maven POM")
    parent = project.find("{*}parent")
    for field in ("groupId", "artifactId", "version"):
        actual = project.findtext("{*}" + field)
        if actual is None and field != "artifactId" and parent is not None:
            actual = parent.findtext("{*}" + field)
        if actual != coordinate[field]:
            raise BundleError(f"POM {field} mismatch for {coordinate['artifactId']}")
    packaging = project.findtext("{*}packaging", "jar")
    if packaging not in ("pom", "jar"):
        raise BundleError("Unsupported packaging: " + packaging)
    owner = target.split("/")[0]
    prefix = "https://maven.pkg.github.com/opaopa6969/"
    for element in project.iter():
        if isinstance(element.tag, str) and element.tag.rsplit("}", 1)[-1] == "url":
            if element.text and element.text.startswith(prefix):
                element.text = "https://maven.pkg.github.com/" + owner + "/" + element.text[len(prefix):]
    for element in project.findall("{*}distributionManagement/{*}repository/{*}url"):
        element.text = "https://maven.pkg.github.com/" + target
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding="utf-8", xml_declaration=True)
    if prefix.encode() in destination.read_bytes():
        raise BundleError("An unconverted personal registry reference remains in the POM")
    return packaging


def prepare_artifact(coordinate, target, directory, fetch=download):
    relative = validate_coordinate(coordinate)
    url = SOURCES[coordinate["source"]] + "/" + relative
    original = directory / "originals" / (relative + ".pom")
    fetch(url + ".pom", original)
    pom = directory / "artifacts" / (relative + ".pom")
    packaging = migrate_pom(original, pom, coordinate, target)
    files = [{"path": str(pom.relative_to(directory)), "sha256": digest(pom),
              "size": pom.stat().st_size, "extension": "pom", "classifier": "",
              "sourceUrl": url + ".pom", "sourceSha256": digest(original),
              "sourcePath": str(original.relative_to(directory))}]
    if packaging == "jar":
        for classifier in ("", "sources", "javadoc"):
            suffix = ("-" + classifier if classifier else "") + ".jar"
            file = directory / "artifacts" / (relative + suffix)
            if fetch(url + suffix, file, optional=bool(classifier)):
                files.append({"path": str(file.relative_to(directory)), "sha256": digest(file),
                              "size": file.stat().st_size, "extension": "jar", "classifier": classifier,
                              "sourceUrl": url + suffix, "sourceSha256": digest(file)})
    return {**coordinate, "packaging": packaging, "files": files}


def prepare_bundle(coordinates, target, output, fetch=download):
    target_repository(target)
    paths = [validate_coordinate(coordinate) for coordinate in coordinates]
    if len(paths) != len(set(paths)) or not paths:
        raise BundleError("Artifact coordinates must be non-empty and unique")
    if output.exists() or output.with_suffix(".json").exists():
        raise BundleError("Output already exists; choose a new destination")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Failed downloads do not leave a publishable partial bundle.
    with tempfile.TemporaryDirectory(prefix="maven-migration-", dir=output.parent) as temporary:
        directory = Path(temporary)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(prepare_artifact, c, target, directory, fetch) for c in coordinates]
            artifacts = [future.result() for future in futures]
        manifest = {"schemaVersion": 1, "targetRepository": target, "artifacts": artifacts}
        manifest_path = directory / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        archive_path = directory / "bundle.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.write(manifest_path, "manifest.json")
            for artifact in artifacts:
                for file in artifact["files"]:
                    archive.write(directory / file["path"], file["path"])
                    if "sourcePath" in file:
                        archive.write(directory / file["sourcePath"], file["sourcePath"])
        manifest["bundleSha256"] = digest(archive_path)
        archive_path.rename(output)
        output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinates", type=Path, required=True)
    parser.add_argument("--target-repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = prepare_bundle(json.loads(args.coordinates.read_text()), args.target_repository, args.output)
    except (BundleError, ET.ParseError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"Prepared {len(manifest['artifacts'])} artifacts for {manifest['targetRepository']}")
    print("Bundle SHA-256: " + manifest["bundleSha256"])


if __name__ == "__main__":
    main()
