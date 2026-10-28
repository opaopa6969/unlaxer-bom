#!/usr/bin/env python3
"""Check the managed account's read access without publishing or exposing tokens."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request


class AccessError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        # Never forward a credential to a redirect target.
        return None


def request_json(token, path):
    request = urllib.request.Request(
        "https://api.github.com/" + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "unlaxer-package-access-check"},
    )
    try:
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Error bodies can contain sensitive request information; do not print them.
        status = error.code
        error.close()
        raise AccessError(f"{path}: HTTP {status}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise AccessError(f"{path}: request failed") from None


def check_access(token, owner, expected_login, config, fetch=request_json):
    if not token:
        raise AccessError("CAULIS_PACKAGES_READ_TOKEN is not available to this repository")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", owner):
        raise AccessError("Invalid registry owner")
    login = fetch(token, "user").get("login")
    if not expected_login or login != expected_login:
        raise AccessError("Authenticated account does not match PACKAGES_READ_ACCOUNT")

    repositories = config["source_repositories"]
    errors = []
    for repository in repositories:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
            raise AccessError("Invalid source repository")
        try:
            # A contents request proves source read access, not just metadata access.
            fetch(token, f"repos/{owner}/{repository}/contents/")
        except AccessError as error:
            errors.append(str(error))

    snapshot_repo = config["snapshot_repository"]
    if snapshot_repo not in repositories:
        raise AccessError("Snapshot repository is not in the source allowlist")
    tag = config["snapshot_tag"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", tag):
        raise AccessError("Invalid snapshot tag")
    try:
        release = fetch(token, f"repos/{owner}/{snapshot_repo}/releases/tags/{tag}")
        available = {asset["name"] for asset in release.get("assets", [])}
        missing = sorted(set(config["snapshot_assets"]) - available)
        if missing:
            errors.append("Snapshot assets missing: " + ", ".join(missing))
    except AccessError as error:
        errors.append(str(error))

    packages = []
    try:
        page = 1
        while True:
            batch = fetch(token, f"orgs/{owner}/packages?package_type=maven&per_page=100&page={page}")
            for package in batch:
                repository = (package.get("repository") or {}).get("name")
                if repository in repositories:
                    packages.append({"name": package["name"], "repository": repository,
                                     "version_count": package["version_count"]})
            if len(batch) < 100:
                break
            page += 1
    except AccessError as error:
        errors.append(str(error))
    if errors:
        raise AccessError("\n".join(errors))
    return {"account": login, "registry_owner": owner,
            "readable_repositories": repositories, "packages": packages,
            "snapshot_tag": tag, "snapshot_assets": sorted(available)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/package-access.json"))
    parser.add_argument("--output", type=Path, default=Path("package-access-report.json"))
    args = parser.parse_args()
    try:
        report = check_access(os.environ.get("GH_TOKEN", ""),
                              os.environ.get("REGISTRY_OWNER", "caulis"),
                              os.environ.get("EXPECTED_LOGIN", ""),
                              json.loads(args.config.read_text()))
    except AccessError as error:
        print(str(error), file=sys.stderr)
        return 1
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Read access verified for {report['account']}: "
          f"{len(report['readable_repositories'])} repositories; "
          f"{len(report['packages'])} existing Maven packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
