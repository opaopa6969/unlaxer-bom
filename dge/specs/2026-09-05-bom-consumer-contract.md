# 実装仕様 — BOM consumer 契約検証（GAP-01 / issue #9）

- 由来: [dge/decisions/2026-09-05-bom-consumer-contract.md](../decisions/2026-09-05-bom-consumer-contract.md)
- 会話劇: [dge/sessions/2026-09-05-bom-consumer-contract.md](../sessions/2026-09-05-bom-consumer-contract.md)

## 1. 追加する原語（1 つだけ）

> **BOM の pin は、実際に解決でき、使える。**

`scripts/verify-bom-consumer-contract.py`。BOM の読み取りは
`scripts/check-bom-version-drift.py` の `managed_versions()` / `parse_pom()` /
`dependency_elements()` / `coordinate()` を import して共有する（別実装を作らない）。

### 不変条件（テストで固定する）

1. `bom registry:` コメントは drift checker の `bom 例外:` パターンを発火させない
2. managed 座標に `bom registry` 宣言が無ければ fatal（座標を名指しする）
3. 宣言値は `central` / `github` のみ。他は fatal
4. `central` 宣言が 1 件も無ければ fatal（検証が空になる抜け道を塞ぐ）
5. exit code は 0 / 1 / 2 の 3 値で、意味が固定される

## 2. `pom.xml` の変更

managed な 12 dependency それぞれに、pin の直後へ 1 行足す。**追加はコメントのみ。**

```xml
<dependency>
    <groupId>org.unlaxer</groupId>
    <artifactId>unlaxer-common</artifactId>
    <version>${unlaxer-common.version}</version>
    <!-- bom registry: central -->
</dependency>
```

| 宣言 | 座標 |
|------|------|
| `central` | `org.unlaxer:unlaxer-common`, `org.seasar.doma:doma-core`, `org.seasar.doma:doma-processor`, `org.flywaydb:flyway-core`, `org.flywaydb:flyway-database-postgresql` |
| `github` | `org.unlaxer:japanese-parser-common`, `org.unlaxer:building-hierarchy`, `org.unlaxer.geo:abr-utils`, `org.unlaxer:onigiri-parser`, `org.unlaxer:historical-town-names`, `org.unlaxer:municipality-history`, `org.unlaxer:japanpost-history` |

## 3. スクリプトの動作

### 3.1 前提確認（失敗は exit 2）

`mvn -v` が成功し Java が使えること。失敗したら「実行不能」として理由付きで 2 を返す。

### 3.2 隔離

`--repo-local` 未指定なら temp ディレクトリを作り `-Dmaven.repo.local` に渡す。
`~/.m2` は読まない・書かない。実行終了時に temp を消す（`--keep` で残せる）。

### 3.3 BOM の install

`mvn -B -N install` を repo root で実行し、対象 commit の BOM を隔離 repo に入れる。

### 3.4 consumer の生成

temp に最小 downstream consumer を作る。

- `dependencyManagement` に BOM を `<type>pom</type><scope>import</scope>` で import
  （version は BOM 自身の `<version>` から取る）
- `<dependencies>` に **`central` 宣言の座標のみ**を **version 無し**で列挙
- `maven.compiler.release` は 21（CI の JDK と一致させる）
- `src/main/java/BomConsumerContract.java` に契約クラスを置く:

```java
import org.unlaxer.CodePointIndex;
import org.seasar.doma.Dao;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationVersion;
```

`CodePointIndex.of(int)` と `CodePointIndex.ZERO` を必ず参照する。
**創業事故（CHANGELOG `[2026.48]`）で欠けていたのがこの 2 つ**であり、
version 照合では検出できずここでだけ捕まる。

### 3.5 injection 契約（全座標）

`mvn help:effective-pom -Doutput=...` を consumer で実行し、
effective POM の `dependencyManagement` を読む。

- managed 12 座標すべてが存在し、version が BOM の pin と一致すること
- version を省略した `<dependencies>` の各項目にも pin が入っていること

第三者 artifact を解決しないため、`github` 側の 7 座標もここで検証される。

### 3.6 resolution + compile 契約（`central` 座標）

consumer で `mvn -B compile` を実行する。resolve と compile が同時に検証される。
失敗したら Maven の stderr / stdout の該当行を出力に含める（どの座標がどこで見つからなかったか）。

### 3.7 `github` 座標の扱い

既定では解決を試みず、`UNVERIFIED (github packages / 認証が必要)` として**座標ごとに列挙**する。
`--include-github` を渡し、かつ環境変数 `GH_PKG_USER` / `GH_PKG_TOKEN` があるときだけ検証対象に含める。
**トークンは CLI 引数で受け取らない。** 生成する `settings.xml` は隔離 temp 内に置き、
出力・ログに値を書かない。

### 3.8 出力

座標ごとに 1 行の表を出し、最後に要約する。

```
座標                                            pin        injection  resolution
org.unlaxer:unlaxer-common                      3.0.11     OK         OK (central)
org.unlaxer:building-hierarchy                  0.19.4     OK         UNVERIFIED (github packages / 認証が必要)
...
契約成立: injection 12/12、resolution 5/12 検証済み・7 未検証(github)
```

### 3.9 exit code

| code | 意味 |
|------|------|
| 0 | 契約成立 |
| 1 | 契約違反（injection 不一致 / resolution・compile 失敗 / registry 未宣言・不正 / central が 0 件） |
| 2 | 実行不能（Java・Maven 不在、Maven Central へ到達できない、BOM の install 失敗） |

## 4. 変えないもの（受け入れ条件）

- `scripts/check-bom-version-drift.py` は 1 行も変えない
- `pom.xml` の座標・version・property・`distributionManagement` を変えない（追加はコメントのみ）
- 既存 12 テストが green のまま
- CI に secret を追加しない

## 5. テスト

### 5.1 unit（`tests/test_verify_bom_consumer_contract.py`・Maven を呼ばない）

| # | 種別 | 内容 |
|---|------|------|
| 1 | normal | `bom registry: central` / `github` を正しく読む |
| 2 | failure | registry 未宣言の座標を fatal にし、座標名を含むメッセージを出す |
| 3 | failure | 未知の registry 値（例 `nexus`）を fatal にする |
| 4 | failure | `central` が 1 件も無い BOM を fatal にする |
| 5 | compat | `bom registry:` コメントが drift checker の `has_reasoned_exception()` を発火させない |
| 6 | compat | `bom 例外:` コメントは従来どおり drift の例外として効く |
| 7 | normal | 生成 consumer POM が BOM を `import` scope で参照し、central 座標を version 無しで宣言する |
| 8 | boundary | 生成 consumer POM に `github` 座標を含めない |
| 9 | normal | effective POM 照合が pin 一致を OK と判定する |
| 10 | failure | effective POM の version が pin と違えば違反として報告する |
| 11 | boundary | effective POM に managed 座標が欠けていれば違反として報告する |
| 12 | boundary | 実行不能（Maven 不在）を exit 2 として区別する |

### 5.2 E2E（CI + 手動。実 artifact を操作する）

```bash
python3 scripts/verify-bom-consumer-contract.py
```

unittest には含めない（ネットワークと Maven に依存し、ローカルの単体テストを遅くするため）。
既存の `check-bom-version-drift.py --bom pom.xml pom.xml` と同じく CI の独立 step として回す。

### 5.3 手で確認する回帰

- 架空 pin（`building-hierarchy 0.19.5` 相当を `central` 座標で再現）で exit 1 になること
- `~/.m2` が変更されないこと
- 同一 commit の再実行が同じ結果を返すこと

## 6. CI

`.github/workflows/ci.yml`:

- 先頭コメントの「dependencyManagement の解決可否を検証する」を、実装が伴う記述に直す
- step を 1 つ追加（secret 不要）:

```yaml
      - name: Verify BOM consumer contract
        run: python3 scripts/verify-bom-consumer-contract.py
```

## 7. README

「### consumer の明示 version drift を検査する」の隣に
「### BOM の pin が実際に解決でき compile できるか検証する」を追加し、
実行方法・`bom registry` 宣言の意味・認証が要る座標の扱いを書く。

## 8. 巻き戻し

PR の revert のみ。decision の「巻き戻し」節を参照。
