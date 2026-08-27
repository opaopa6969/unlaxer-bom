#!/usr/bin/env python3
"""BOM の pin と consumer POM の明示 version の不一致を検出する。

unlaxer-bom を import しているかどうかは判定に影響しない。BOM が管理する
groupId/artifactId を consumer が異なる version で直接指定した場合に失敗する。
意図的な先行検証などは、該当 dependency 内に理由付きコメントを置く:

    <!-- bom 例外: unlaxer-bom #123 がリリースされるまでの先行検証 -->

入口は手動/CI、git pre-commit (--staged)、Claude Code PreToolUse (--hook) の3つ。
Python 標準ライブラリだけで動作する。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


EXCEPTION_PATTERN = re.compile(r"bom\s*例外\s*:\s*(.+)", re.DOTALL)
PROPERTY_PATTERN = re.compile(r"\$\{([^}]+)}")
SKIP_DIRECTORIES = {".git", "target", "node_modules", "out", "vendor"}
PLACEHOLDER_REASONS = {"todo", "tbd", "理由", "reason", "none", "n/a"}


class PomError(ValueError):
    """POM を安全に比較できない場合。"""


def local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if local_name(item.tag) == name), None)


def child_text(element: ET.Element, name: str) -> str | None:
    item = child(element, name)
    if item is None or item.text is None:
        return None
    value = item.text.strip()
    return value or None


def parse_pom(path: Path) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    try:
        return ET.parse(path, parser=parser).getroot()
    except (ET.ParseError, OSError) as error:
        raise PomError(f"{path}: POM を読めません: {error}") from error


def project_properties(project: ET.Element) -> dict[str, str]:
    properties: dict[str, str] = {}
    properties_element = child(project, "properties")
    if properties_element is not None:
        for item in properties_element:
            if isinstance(item.tag, str) and item.text is not None:
                properties[local_name(item.tag)] = item.text.strip()

    parent = child(project, "parent")
    project_version = child_text(project, "version")
    project_group = child_text(project, "groupId")
    if project_version is None and parent is not None:
        project_version = child_text(parent, "version")
    if project_group is None and parent is not None:
        project_group = child_text(parent, "groupId")
    if project_version:
        properties.update({"project.version": project_version, "pom.version": project_version})
    if project_group:
        properties.update({"project.groupId": project_group, "pom.groupId": project_group})
    return properties


def resolve(value: str, properties: dict[str, str]) -> str | None:
    """POM 内で完結する property を再帰的に解決する。循環・外部 property は None。"""
    current = value.strip()
    seen: set[str] = set()
    for _ in range(50):
        matches = PROPERTY_PATTERN.findall(current)
        if not matches:
            return current
        state = current
        if state in seen:
            return None
        seen.add(state)
        for name in matches:
            replacement = properties.get(name)
            if replacement is None:
                return None
            current = current.replace("${" + name + "}", replacement)
    return None


def dependency_elements(project: ET.Element, *, managed: bool | None) -> list[ET.Element]:
    """plugin dependency を除き、通常/profile の Maven dependency を返す。"""
    found: list[ET.Element] = []

    def visit(element: ET.Element, inside_management: bool = False) -> None:
        name = local_name(element.tag)
        next_inside_management = inside_management or name == "dependencyManagement"
        if name == "dependencies":
            for item in element:
                if (
                    local_name(item.tag) == "dependency"
                    and (managed is None or next_inside_management == managed)
                ):
                    found.append(item)
            return
        if name in {"build", "reporting"}:
            return
        for item in element:
            if isinstance(item.tag, str):
                visit(item, next_inside_management)

    visit(project)
    return found


def coordinate(dependency: ET.Element, properties: dict[str, str]) -> tuple[str, str] | None:
    group = child_text(dependency, "groupId")
    artifact = child_text(dependency, "artifactId")
    if group is None or artifact is None:
        return None
    resolved_group = resolve(group, properties)
    resolved_artifact = resolve(artifact, properties)
    if resolved_group is None or resolved_artifact is None:
        return None
    return resolved_group, resolved_artifact


def has_reasoned_exception(dependency: ET.Element) -> bool:
    for item in dependency.iter():
        if item.tag is ET.Comment and item.text:
            match = EXCEPTION_PATTERN.search(item.text.strip())
            if match:
                reason = match.group(1).strip()
                if len(reason) >= 4 and reason.lower() not in PLACEHOLDER_REASONS:
                    return True
    return False


def managed_versions(bom_path: Path) -> dict[tuple[str, str], str]:
    project = parse_pom(bom_path)
    properties = project_properties(project)
    managed: dict[tuple[str, str], str] = {}
    for dependency in dependency_elements(project, managed=True):
        key = coordinate(dependency, properties)
        raw_version = child_text(dependency, "version")
        if key is None or raw_version is None:
            continue
        version = resolve(raw_version, properties)
        if version is None:
            raise PomError(
                f"{bom_path}: {key[0]}:{key[1]} の BOM version {raw_version!r} を解決できません"
            )
        previous = managed.get(key)
        if previous is not None and previous != version:
            raise PomError(
                f"{bom_path}: {key[0]}:{key[1]} に複数の BOM pin ({previous}, {version}) があります"
            )
        managed[key] = version
    if not managed:
        raise PomError(f"{bom_path}: dependencyManagement の version 付き依存がありません")
    return managed


def drift_messages(
    consumer_path: Path,
    managed: dict[tuple[str, str], str],
    *,
    display_path: str | None = None,
) -> list[str]:
    project = parse_pom(consumer_path)
    properties = project_properties(project)
    shown = display_path or str(consumer_path)
    violations: list[str] = []
    for dependency in dependency_elements(project, managed=None):
        key = coordinate(dependency, properties)
        raw_version = child_text(dependency, "version")
        if key is None or raw_version is None or key not in managed:
            continue
        actual = resolve(raw_version, properties)
        expected = managed[key]
        if actual == expected or has_reasoned_exception(dependency):
            continue
        coordinate_text = f"{key[0]}:{key[1]}"
        if actual is None:
            difference = f"明示 version {raw_version!r} は POM 内で解決不能; BOM={expected}"
        else:
            difference = f"明示 version={actual}; BOM={expected}"
        violations.append(f"{shown}: {coordinate_text}: {difference}")
    return violations


def report(violations: list[str], *, hook: bool = False) -> int:
    if not violations:
        return 0
    print("BOM pin と異なる明示 version を検出しました:", file=sys.stderr)
    for violation in violations:
        print(f"  {violation}", file=sys.stderr)
    print(
        "\nversion を BOM に合わせるか省略してください。意図的な差分なら該当 dependency 内に\n"
        "`<!-- bom 例外: 理由 -->` を追加してください（理由は4文字以上）。",
        file=sys.stderr,
    )
    return 2 if hook else 1


def repository_root(start: Path) -> Path:
    current = start.resolve() if start.is_dir() else start.resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    raise PomError(f"{start}: git repository が見つかりません")


def repository_poms(root: Path) -> list[Path]:
    result: list[Path] = []
    for directory, names, files in os.walk(root):
        names[:] = [name for name in names if name not in SKIP_DIRECTORIES]
        if "pom.xml" in files:
            result.append(Path(directory) / "pom.xml")
    return sorted(result)


def run_files(bom: Path, consumers: list[Path]) -> int:
    managed = managed_versions(bom)
    violations: list[str] = []
    for consumer in consumers:
        violations.extend(drift_messages(consumer, managed))
    return report(violations)


def git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=root, text=True, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise PomError(completed.stderr.strip() or f"git {' '.join(arguments)} に失敗しました")
    return completed.stdout


def run_staged(bom_path: Path) -> int:
    """index 上の全 tracked POM を比較し、unstaged 内容を混ぜない。"""
    root = repository_root(Path.cwd())
    names = [name for name in git_output(root, "ls-files", "*pom.xml").splitlines() if name]
    if not names:
        return 0
    with tempfile.TemporaryDirectory(prefix="bom-drift-staged-") as directory:
        temporary_root = Path(directory)
        for name in names:
            target = temporary_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(git_output(root, "show", f":{name}"), encoding="utf-8")
        resolved_bom = bom_path.resolve()
        try:
            bom_name = str(resolved_bom.relative_to(root)).replace(os.sep, "/")
        except ValueError:
            bom_name = None
        staged_bom = temporary_root / bom_name if bom_name in names else resolved_bom
        managed = managed_versions(staged_bom)
        violations: list[str] = []
        for name in names:
            violations.extend(
                drift_messages(temporary_root / name, managed, display_path=name)
            )
        return report(violations)


def prospective_content(path: Path, tool_input: dict[str, object]) -> str | None:
    content = tool_input.get("content")
    if isinstance(content, str):
        return content
    new_string = tool_input.get("new_string")
    old_string = tool_input.get("old_string")
    if not isinstance(new_string, str) or not isinstance(old_string, str) or not path.exists():
        return None
    current = path.read_text(encoding="utf-8")
    count = -1 if tool_input.get("replace_all") is True else 1
    if old_string not in current:
        return None
    return current.replace(old_string, new_string, count)


def run_hook(bom_path: Path) -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    raw_path = tool_input.get("file_path")
    if not isinstance(raw_path, str) or Path(raw_path).name != "pom.xml":
        return 0
    path = Path(raw_path).resolve()
    content = prospective_content(path, tool_input)
    if content is None:
        return 0
    root = repository_root(path)
    with tempfile.TemporaryDirectory(prefix="bom-drift-hook-") as directory:
        proposed = Path(directory) / "pom.xml"
        proposed.write_text(content, encoding="utf-8")
        resolved_bom = bom_path.resolve()
        editing_bom = path == resolved_bom
        bom = proposed if editing_bom else resolved_bom
        managed = managed_versions(bom)
        violations: list[str] = []
        if editing_bom:
            for consumer in repository_poms(root):
                if consumer != path:
                    violations.extend(
                        drift_messages(consumer, managed, display_path=str(consumer.relative_to(root)))
                    )
        else:
            violations.extend(
                drift_messages(proposed, managed, display_path=str(path.relative_to(root)))
            )
        return report(violations, hook=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="git index 上の全 POM を検査する")
    mode.add_argument("--hook", action="store_true", help="Claude Code PreToolUse hook として動く")
    parser.add_argument("--bom", type=Path, default=Path("pom.xml"), help="基準 BOM POM")
    parser.add_argument("poms", nargs="*", type=Path, help="検査する consumer POM")
    arguments = parser.parse_args()
    try:
        if arguments.staged:
            return run_staged(arguments.bom)
        if arguments.hook:
            return run_hook(arguments.bom)
        consumers = arguments.poms or [arguments.bom]
        return run_files(arguments.bom, consumers)
    except PomError as error:
        print(f"BOM drift checker error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
