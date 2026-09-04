#!/usr/bin/env python3
"""BOM の pin が実際に解決でき、compile できることを検証する。

check-bom-version-drift.py が「BOM を真実として consumer の書き方を静的に正す」のに対し、
こちらは「BOM の pin 自身が下流で成立するか」を実際に Maven を回して確かめる。
増える原語は 1 つだけ: **BOM の pin は、実際に解決でき、使える**。

検証は 2 軸に分ける。

1. injection 契約 — BOM を <scope>import</scope> した最小 downstream consumer を実 build し、
   effective POM 上で全 managed 座標の version が pin と一致することを確かめる。
   Maven の model 解決だけで済むので、第三者 artifact を1つも落とさずに全座標を見られる。
2. resolution + compile 契約 — pin が実在して resolve でき、その jar に対して compile が通るか。
   registry と認証に依存するため、pom.xml の `bom registry:` 宣言で対象を分ける。
   central は secret 無しで常時検証し、github は既定で「未検証」と明示的に報告する
   （黙って skip しない）。

compile まで行うのは、version 文字列の比較では原理的に検出できない事故があるため。
CHANGELOG [2026.48] の unlaxer-common 2.8.0 は GitHub Packages と Maven Central に
同じ座標で中身違いで存在し、Central 側に CodePointIndex.of / ZERO が無かった。
resolve は成功して compile だけが落ちる型で、ここでだけ捕まる。

exit code:
    0  契約成立
    1  契約違反（injection 不一致 / resolve・compile 失敗 / registry 宣言の不備）
    2  実行不能（Java・Maven 不在、Maven Central へ到達不可、BOM の install 失敗）

Python 標準ライブラリだけで動作する。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


SCRIPT_DIRECTORY = Path(__file__).resolve().parent

# BOM の読み取りは既存 checker と共有する（判定を緩めた別実装を作らない）。
_SPEC = importlib.util.spec_from_file_location(
    "check_bom_version_drift", SCRIPT_DIRECTORY / "check-bom-version-drift.py"
)
drift = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(drift)

PomError = drift.PomError

REGISTRY_PATTERN = re.compile(r"bom\s+registry\s*:\s*([A-Za-z0-9_.\-]+)")
VALID_REGISTRIES = ("central", "github")
CENTRAL_PROBE_URL = "https://repo.maven.apache.org/maven2/"

# 再実行の決定性のため plugin version を固定する（既定版は Maven の版に依存するため）。
HELP_PLUGIN = "org.apache.maven.plugins:maven-help-plugin:3.5.1"
COMPILER_PLUGIN_VERSION = "3.13.0"
COMPILER_RELEASE = "21"

# central 宣言の座標が提供する型を実際に触る断片。座標が central でなくなれば自動で外れる。
CONTRACT_SNIPPETS: dict[tuple[str, str], str] = {
    # 創業事故（CHANGELOG [2026.48]）で Central 側の 2.8.0 に欠けていた of / ZERO を必ず参照する。
    ("org.unlaxer", "unlaxer-common"): (
        "        touched(org.unlaxer.CodePointIndex.of(1));\n"
        "        touched(org.unlaxer.CodePointIndex.ZERO);\n"
    ),
    ("org.seasar.doma", "doma-core"): "        touched(org.seasar.doma.Dao.class);\n",
    ("org.flywaydb", "flyway-core"): (
        "        touched(org.flywaydb.core.Flyway.configure());\n"
        "        touched(org.flywaydb.core.api.MigrationVersion.LATEST);\n"
    ),
}

# 「確かめられなかった」を「壊れている」と混同しないための分類。先に評価する。
UNRUNNABLE_MARKERS = (
    "offline mode",
    "Could not transfer artifact",
    "UnknownHostException",
    "Connection refused",
    "Connection timed out",
    "Network is unreachable",
    "No route to host",
    "Read timed out",
    "SocketTimeoutException",
    "PKIX path building failed",
)


class ContractViolation(Exception):
    """BOM の契約が成立していない（exit 1）。"""


class Unrunnable(Exception):
    """契約を確かめられない（exit 2）。"""


def local_name(tag: object) -> str:
    return drift.local_name(tag)


def bom_identity(project: ET.Element) -> tuple[str, str, str]:
    group = drift.child_text(project, "groupId")
    artifact = drift.child_text(project, "artifactId")
    version = drift.child_text(project, "version")
    if not group or not artifact or not version:
        raise PomError("BOM の groupId / artifactId / version を読めません")
    return group, artifact, version


def distribution_repository(project: ET.Element) -> tuple[str, str] | None:
    """distributionManagement の repository を (id, url) で返す（github 検証で再利用する）。"""
    management = drift.child(project, "distributionManagement")
    if management is None:
        return None
    repository = drift.child(management, "repository")
    if repository is None:
        return None
    identifier = drift.child_text(repository, "id")
    url = drift.child_text(repository, "url")
    if not identifier or not url:
        return None
    return identifier, url


def registry_declarations(project: ET.Element) -> dict[tuple[str, str], str]:
    """dependencyManagement の各 dependency から `bom registry:` 宣言を読む。"""
    properties = drift.project_properties(project)
    declarations: dict[tuple[str, str], str] = {}
    for dependency in drift.dependency_elements(project, managed=True):
        key = drift.coordinate(dependency, properties)
        if key is None:
            continue
        for item in dependency.iter():
            if item.tag is ET.Comment and item.text:
                match = REGISTRY_PATTERN.search(item.text)
                if match:
                    declarations[key] = match.group(1)
                    break
    return declarations


def classify_registries(
    managed: dict[tuple[str, str], str], declarations: dict[tuple[str, str], str]
) -> dict[str, list[tuple[str, str]]]:
    """managed 座標を registry ごとに分ける。宣言の不備は契約違反。"""
    undeclared = sorted(key for key in managed if key not in declarations)
    if undeclared:
        listed = "\n".join(f"  {group}:{artifact}" for group, artifact in undeclared)
        raise ContractViolation(
            "`bom registry:` 宣言の無い managed 座標があります。pom.xml の該当 dependency に\n"
            "`<!-- bom registry: central -->` か `<!-- bom registry: github -->` を追加してください:\n"
            f"{listed}"
        )
    unknown = sorted(
        (key, value) for key, value in declarations.items()
        if key in managed and value not in VALID_REGISTRIES
    )
    if unknown:
        listed = "\n".join(f"  {g}:{a}: {value!r}" for (g, a), value in unknown)
        raise ContractViolation(
            f"未知の `bom registry` 値です（使えるのは {' / '.join(VALID_REGISTRIES)}）:\n{listed}"
        )
    buckets: dict[str, list[tuple[str, str]]] = {name: [] for name in VALID_REGISTRIES}
    for key in managed:
        buckets[declarations[key]].append(key)
    for name in buckets:
        buckets[name].sort()
    if not buckets["central"]:
        raise ContractViolation(
            "`bom registry: central` の座標が 1 件もありません。全座標が認証必須になると"
            "この検証は空になります。少なくとも 1 件は secret 無しで検証できる必要があります。"
        )
    return buckets


def consumer_pom(
    bom: tuple[str, str, str],
    coordinates: list[tuple[str, str]],
    extra_repository: tuple[str, str] | None,
) -> str:
    """最小 downstream consumer。BOM を import し、対象座標を version 無しで宣言する。"""
    group, artifact, version = bom
    declared = "\n".join(
        f"    <dependency>\n"
        f"      <groupId>{dependency_group}</groupId>\n"
        f"      <artifactId>{dependency_artifact}</artifactId>\n"
        f"    </dependency>"
        for dependency_group, dependency_artifact in coordinates
    )
    repositories = ""
    if extra_repository is not None:
        identifier, url = extra_repository
        repositories = (
            "\n  <repositories>\n"
            "    <repository>\n"
            f"      <id>{identifier}</id>\n"
            f"      <url>{url}</url>\n"
            "    </repository>\n"
            "  </repositories>\n"
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- scripts/verify-bom-consumer-contract.py が生成した最小 downstream consumer。手で編集しない。 -->
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.unlaxer.bomcontract</groupId>
  <artifactId>bom-consumer-contract</artifactId>
  <version>0-SNAPSHOT</version>
  <packaging>jar</packaging>

  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <maven.compiler.release>{COMPILER_RELEASE}</maven.compiler.release>
  </properties>
{repositories}
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>{group}</groupId>
        <artifactId>{artifact}</artifactId>
        <version>{version}</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>

  <!-- version は書かない。BOM の pin が注入されることそのものが検証対象。 -->
  <dependencies>
{declared}
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>{COMPILER_PLUGIN_VERSION}</version>
        <configuration>
          <!-- doma-processor が classpath に載るため、注釈処理は明示的に止める。 -->
          <proc>none</proc>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
"""


def contract_source(coordinates: list[tuple[str, str]]) -> str:
    """解決された jar の中身に触る契約クラス。座標が減れば参照も自動で減る。"""
    body = "".join(CONTRACT_SNIPPETS[key] for key in coordinates if key in CONTRACT_SNIPPETS)
    return f"""// scripts/verify-bom-consumer-contract.py が生成。手で編集しない。
// 同一座標・中身違いの artifact（CHANGELOG [2026.48]）は version 比較では検出できない。
// 解決された jar の型に実際に触ることでだけ捕まる。
public final class BomConsumerContract {{
    private BomConsumerContract() {{}}

    private static void touched(Object value) {{
        if (value == null) {{
            throw new IllegalStateException("BOM が固定した型を解決できませんでした");
        }}
    }}

    public static void main(String[] arguments) {{
{body}    }}
}}
"""


def settings_xml(server_id: str | None) -> str:
    """利用者の ~/.m2/settings.xml（mirror 等）に結果が依存しないよう、隔離した settings を使う。

    認証情報は Maven の ${env.*} 補間に任せ、値をこのプロセスにもディスクにも持たない。
    """
    servers = ""
    if server_id is not None:
        servers = (
            "  <servers>\n"
            "    <server>\n"
            f"      <id>{server_id}</id>\n"
            "      <username>${env.GH_PKG_USER}</username>\n"
            "      <password>${env.GH_PKG_TOKEN}</password>\n"
            "    </server>\n"
            "  </servers>\n"
        )
    return f"<settings>\n{servers}</settings>\n"


def maven_executable() -> str:
    executable = shutil.which("mvn")
    if executable is None:
        raise Unrunnable("mvn が見つかりません。Maven を PATH に通してください。")
    return executable


def run_maven(arguments: list[str], *, cwd: Path, repo_local: Path, settings: Path) -> tuple[int, str]:
    completed = subprocess.run(
        [
            maven_executable(),
            "-B",
            "-s",
            str(settings),
            f"-Dmaven.repo.local={repo_local}",
            *arguments,
        ],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout + completed.stderr


def maven_failure(action: str, output: str) -> Exception:
    """Maven の失敗を「壊れている」と「確かめられなかった」に分ける。"""
    tail = "\n".join(
        line for line in output.splitlines() if line.startswith("[ERROR]") or "ERROR" in line
    )[-4000:]
    if not tail:
        tail = output[-2000:]
    if any(marker in output for marker in UNRUNNABLE_MARKERS):
        return Unrunnable(f"{action} を完了できませんでした（ネットワーク・認証・環境の問題）:\n{tail}")
    return ContractViolation(f"{action} が失敗しました:\n{tail}")


def read_effective_pom(path: Path) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    """effective POM から dependencyManagement と dependencies の version を取る。"""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise Unrunnable(f"effective POM を読めません: {error}") from error

    def collect(container: ET.Element) -> dict[tuple[str, str], str]:
        found: dict[tuple[str, str], str] = {}
        for dependency in container:
            if local_name(dependency.tag) != "dependency":
                continue
            group = drift.child_text(dependency, "groupId")
            artifact = drift.child_text(dependency, "artifactId")
            version = drift.child_text(dependency, "version")
            if group and artifact:
                found[(group, artifact)] = version or ""
        return found

    management: dict[tuple[str, str], str] = {}
    dependencies: dict[tuple[str, str], str] = {}
    for element in root:
        name = local_name(element.tag)
        if name == "dependencyManagement":
            inner = drift.child(element, "dependencies")
            if inner is not None:
                management = collect(inner)
        elif name == "dependencies":
            dependencies = collect(element)
    return management, dependencies


def check_injection(
    managed: dict[tuple[str, str], str],
    management: dict[tuple[str, str], str],
    dependencies: dict[tuple[str, str], str],
    declared: list[tuple[str, str]],
) -> None:
    problems: list[str] = []
    for key, pin in sorted(managed.items()):
        name = f"{key[0]}:{key[1]}"
        effective = management.get(key)
        if effective is None:
            problems.append(f"  {name}: import した BOM の effective dependencyManagement に現れません")
        elif effective != pin:
            problems.append(f"  {name}: effective={effective}; BOM pin={pin}")
    for key in declared:
        name = f"{key[0]}:{key[1]}"
        effective = dependencies.get(key)
        pin = managed[key]
        if effective is None:
            problems.append(f"  {name}: version 無しで宣言したが effective dependencies に現れません")
        elif effective != pin:
            problems.append(f"  {name}: version 無し宣言に注入された版={effective}; BOM pin={pin}")
    if problems:
        raise ContractViolation(
            "BOM を import しても pin が注入されていません:\n" + "\n".join(problems)
        )


def probe_central(timeout: float) -> None:
    request = urllib.request.Request(CENTRAL_PROBE_URL, method="HEAD")
    try:
        urllib.request.urlopen(request, timeout=timeout).close()
    except urllib.error.HTTPError:
        return  # 応答があれば到達はできている
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise Unrunnable(
            f"Maven Central ({CENTRAL_PROBE_URL}) に到達できません: {error}\n"
            "契約が壊れているのではなく、確かめられませんでした。"
        ) from error


def require_github_credentials() -> None:
    """環境変数の有無だけを確かめる。値は読まない（プロセスにも出力にも残さないため）。"""
    missing = [name for name in ("GH_PKG_USER", "GH_PKG_TOKEN") if not os.environ.get(name)]
    if missing:
        raise Unrunnable(
            f"--include-github には環境変数 {' と '.join(missing)} が必要です"
            "（トークンは引数では受け取らず、値も読みません）。"
        )


def render(
    managed: dict[tuple[str, str], str],
    verified: set[tuple[str, str]],
) -> str:
    names = {key: f"{key[0]}:{key[1]}" for key in managed}
    width = max(len(name) for name in names.values())
    pin_width = max(len(pin) for pin in managed.values())
    lines = [
        f"{'座標'.ljust(width)}  {'pin'.ljust(pin_width)}  injection  resolution",
    ]
    for key in sorted(managed):
        if key in verified:
            resolution = "OK (central: resolve + compile)"
        else:
            resolution = "UNVERIFIED (github packages / 認証が必要)"
        lines.append(f"{names[key].ljust(width)}  {managed[key].ljust(pin_width)}  OK         {resolution}")
    lines.append("")
    lines.append(
        f"契約成立: injection {len(managed)}/{len(managed)}、"
        f"resolution {len(verified)}/{len(managed)} 検証済み・"
        f"{len(managed) - len(verified)} 未検証(github packages)"
    )
    if len(verified) != len(managed):
        lines.append(
            "未検証の座標は GH_PKG_USER / GH_PKG_TOKEN を設定して --include-github で検証できます。"
        )
    return "\n".join(lines)


def verify(
    bom_path: Path,
    *,
    workspace: Path,
    repo_local: Path,
    include_github: bool,
    timeout: float,
) -> str:
    project = drift.parse_pom(bom_path)
    bom = bom_identity(project)
    managed = drift.managed_versions(bom_path)
    buckets = classify_registries(managed, registry_declarations(project))

    server_id = None
    extra_repository = None
    targets = list(buckets["central"])
    if include_github:
        require_github_credentials()
        repository = distribution_repository(project)
        if repository is None:
            raise Unrunnable(
                "--include-github には BOM の distributionManagement に repository が必要です。"
            )
        extra_repository = repository
        server_id = repository[0]
        targets = sorted(targets + buckets["github"])

    probe_central(timeout)

    settings = workspace / "settings.xml"
    settings.write_text(settings_xml(server_id), encoding="utf-8")

    code, output = run_maven(
        ["-N", "install"], cwd=bom_path.parent, repo_local=repo_local, settings=settings
    )
    if code != 0:
        # BOM 自身が install できないのは「契約が壊れている」ではなく「確かめられない」。
        raise Unrunnable(str(maven_failure("BOM の install", output)))

    consumer = workspace / "consumer"
    source = consumer / "src" / "main" / "java"
    source.mkdir(parents=True, exist_ok=True)
    (consumer / "pom.xml").write_text(
        consumer_pom(bom, targets, extra_repository), encoding="utf-8"
    )
    (source / "BomConsumerContract.java").write_text(contract_source(targets), encoding="utf-8")

    effective = workspace / "effective-pom.xml"
    code, output = run_maven(
        [f"{HELP_PLUGIN}:effective-pom", f"-Doutput={effective}"],
        cwd=consumer,
        repo_local=repo_local,
        settings=settings,
    )
    if code != 0:
        raise maven_failure("consumer の effective POM 生成", output)
    management, dependencies = read_effective_pom(effective)
    check_injection(managed, management, dependencies, targets)

    code, output = run_maven(["compile"], cwd=consumer, repo_local=repo_local, settings=settings)
    if code != 0:
        raise maven_failure("consumer の resolve + compile", output)

    return render(managed, set(targets))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bom", type=Path, default=Path("pom.xml"), help="検証する BOM POM")
    parser.add_argument(
        "--repo-local", type=Path, default=None,
        help="使用する Maven local repository（既定は毎回 temp を作り ~/.m2 を触らない）",
    )
    parser.add_argument("--keep", action="store_true", help="生成した consumer を消さずに残す")
    parser.add_argument(
        "--include-github", action="store_true",
        help="GitHub Packages の座標も検証する（GH_PKG_USER / GH_PKG_TOKEN が必要）",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="Maven Central 到達確認の秒数")
    arguments = parser.parse_args()

    try:
        bom_path = arguments.bom.resolve()
        if not bom_path.is_file():
            raise Unrunnable(f"{arguments.bom}: BOM POM がありません")
        maven_executable()
        directory = tempfile.mkdtemp(prefix="bom-consumer-contract-")
        workspace = Path(directory)
        repo_local = (arguments.repo_local.resolve() if arguments.repo_local
                      else workspace / "repository")
        repo_local.mkdir(parents=True, exist_ok=True)
        try:
            print(verify(
                bom_path,
                workspace=workspace,
                repo_local=repo_local,
                include_github=arguments.include_github,
                timeout=arguments.timeout,
            ))
        finally:
            if arguments.keep:
                print(f"\n生成物を残しました: {workspace}", file=sys.stderr)
            else:
                shutil.rmtree(workspace, ignore_errors=True)
        return 0
    except (ContractViolation, PomError) as error:
        # PomError（POM を読めない / pin の property を解決できない）は BOM 自身の欠陥であり、
        # 「確かめられなかった」ではなく契約が壊れている状態。
        print(f"BOM consumer 契約違反: {error}", file=sys.stderr)
        return 1
    except Unrunnable as error:
        print(f"BOM consumer 契約を検証できません: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
