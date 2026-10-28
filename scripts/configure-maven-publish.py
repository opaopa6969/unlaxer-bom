#!/usr/bin/env python3
"""Configure an isolated checkout to read and publish Maven packages for its owner."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

NS = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", NS)
PREFIX = "https://maven.pkg.github.com/"
PUBLISH_ID = "github-local-publish"


class ConfigurationError(Exception):
    pass


def child(parent, name):
    node = parent.find("{*}" + name)
    return node if node is not None else ET.SubElement(parent, "{" + NS + "}" + name)


def configure(poms, repository, settings, environment):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository):
        raise ConfigurationError("Invalid target repository")
    owner = repository.split("/")[0]
    trees = []
    read_ids = set()
    for path in poms:
        tree = ET.parse(path, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
        project = tree.getroot()
        if project.tag != "{" + NS + "}project":
            raise ConfigurationError("Not a Maven POM: " + str(path))
        # The Central extension replaces Maven's deploy lifecycle, even when an
        # alternate repository is selected. Remove it from this isolated GitHub
        # publishing checkout, including inactive/active profile declarations.
        for plugins in project.findall('.//{*}plugins'):
            for plugin in list(plugins):
                if (plugin.findtext('{*}groupId'), plugin.findtext('{*}artifactId')) == (
                        'org.sonatype.central', 'central-publishing-maven-plugin'):
                    plugins.remove(plugin)
        parents = {node: parent for parent in project.iter() for node in parent}
        for tag in ("repository", "pluginRepository"):
            for node in project.findall(".//{*}" + tag):
                url = node.find("{*}url")
                if url is not None and (url.text or "").strip().startswith(PREFIX):
                    suffix = url.text.strip()[len(PREFIX):].partition("/")[2]
                    if not suffix:
                        raise ConfigurationError("Invalid Packages repository URL")
                    url.text = PREFIX + owner + "/" + suffix
                    # Distribution credentials must never be reused for reads.
                    if parents[node].tag != "{" + NS + "}distributionManagement":
                        server_id = node.findtext("{*}id")
                        if not server_id or server_id == PUBLISH_ID:
                            raise ConfigurationError("Missing or reserved read repository id")
                        read_ids.add(server_id)
        child(project, "distributionManagement")
        for distribution in project.findall(".//{*}distributionManagement"):
            for tag in ("repository", "snapshotRepository"):
                node = distribution.find("{*}" + tag)
                if node is not None or tag == "repository":
                    node = child(distribution, tag)
                    child(node, "id").text = PUBLISH_ID
                    child(node, "name").text = "GitHub Packages (" + repository + ")"
                    child(node, "url").text = PREFIX + repository
        # Pin the deploy plugin so dry-run uses the same modern alt-repository
        # syntax for single-module and reactor projects alike.
        plugins = child(child(project, "build"), "plugins")
        def is_deploy(plugin):
            return (plugin.findtext("{*}artifactId") == "maven-deploy-plugin"
                    and plugin.findtext("{*}groupId", "org.apache.maven.plugins") == "org.apache.maven.plugins")
        if not any(is_deploy(plugin) for plugin in plugins.findall("{*}plugin")):
            plugin = ET.SubElement(plugins, "{" + NS + "}plugin")
            child(plugin, "artifactId").text = "maven-deploy-plugin"
        matches = [p for p in project.findall(".//{*}plugin") if is_deploy(p)]
        for plugin in matches:
            child(plugin, "groupId").text = "org.apache.maven.plugins"
            child(plugin, "artifactId").text = "maven-deploy-plugin"
            child(plugin, "version").text = "3.1.4"
        trees.append((path, tree))

    if not trees:
        raise ConfigurationError("No POM files found")
    required = ["MAVEN_PACKAGES_WRITE_USER", "MAVEN_PACKAGES_WRITE_TOKEN"]
    if read_ids:
        required += ["MAVEN_PACKAGES_READ_USER", "MAVEN_PACKAGES_READ_TOKEN"]
    for name in required:
        if not environment.get(name):
            raise ConfigurationError(name + " is required; configure the repository's Packages credentials")

    settings_tree = ET.Element("settings")
    servers = ET.SubElement(settings_tree, "servers")
    for identifier, role in [(PUBLISH_ID, "WRITE")] + [(key, "READ") for key in sorted(read_ids)]:
        server = ET.SubElement(servers, "server")
        ET.SubElement(server, "id").text = identifier
        ET.SubElement(server, "username").text = "${env.MAVEN_PACKAGES_" + role + "_USER}"
        ET.SubElement(server, "password").text = "${env.MAVEN_PACKAGES_" + role + "_TOKEN}"
    # Finish all validation before modifying any source POM or writing settings.
    settings.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(settings_tree).write(settings, encoding="utf-8", xml_declaration=True)
    settings.chmod(0o600)
    for path, tree in trees:
        tree.write(path, encoding="utf-8", xml_declaration=True)
    return read_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        files = subprocess.check_output(
            ["git", "ls-files", "-z", "--", "pom.xml", "**/pom.xml"], cwd=args.root)
        poms = [args.root / os.fsdecode(path) for path in files.split(b"\0") if path]
        read_ids = configure(poms, args.repository, args.settings, os.environ)
    except (ConfigurationError, ET.ParseError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"Configured {len(poms)} POMs for {args.repository}; {len(read_ids)} private read repositories")


if __name__ == "__main__":
    main()
