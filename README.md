# unlaxer-bom

vacant 製品群の **共通 BOM（検証済みバージョンセット / Bill of Materials）**。
各リポは独立 SemVer のまま、**BOM のバージョン（CalVer `YYYY.MM`）だけがリリーストレイン番号**になる
（Jackson / Spring と同方式）。

> **2層 BOM**: この `unlaxer-bom` は全製品で共有する artifact（common / building-hierarchy / abr-utils /
> onigiri-parser / 予定: jaddress-rdb-api）と検証済み 3rdパーティ（doma / flyway）を固定する**共通 BOM**。
> 製品固有の rdb 実装・service は **製品 BOM**（`vacant-bom` 等、共通 BOM を import する）が固定する。
> 全体設計は [docs/design/vacant-bom-rdb-architecture.md](docs/design/vacant-bom-rdb-architecture.md)。

## なぜ BOM か

バージョン番号をリポ横断でロックステップに揃える案は不採用（開発速度差・独立作業・SemVer 破壊のため）。
代わりに「**どの組み合わせが検証済みか**」を1か所で固定する。
経緯: unlaxer-common の 1.1.26/2.8.0 取り違え事故（古い参照コピーを前提にしてしまった）。

## 使い方

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.unlaxer</groupId>
      <artifactId>unlaxer-bom</artifactId>
      <version>2026.53</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>

<!-- 以降、各依存はバージョン指定なしで BOM の検証済み版が効く -->
<dependencies>
  <dependency>
    <groupId>org.unlaxer</groupId>
    <artifactId>building-hierarchy</artifactId>
  </dependency>
</dependencies>
```

> **これだけでは resolve できない座標がある。** BOM が固定する 12 座標のうち
> **Maven Central にあるのは 5 つだけ**で、残り 7 つ（上の例の `building-hierarchy` を含む）は
> **GitHub Packages にしか無く `read:packages` 認証が要る**。認証が無いと Maven は
> `Could not find artifact ... in central` としか言わず、401 と 404 を区別しない。
> どの座標がどちらかは `pom.xml` の `bom registry:` 宣言か、
> [検証スクリプトの出力](#bom-の-pin-が実際に解決でき-compile-できるか検証する)で確認できる。

#### GitHub Packages 側の座標を使うには

consumer の POM に repository を足し、`read:packages` を持つトークンを settings.xml に置く。
**`<id>` が両方で一致していないと Maven は資格情報を送らない**（無言で 401 → 「見つからない」になる）。

```xml
<!-- consumer の pom.xml -->
<repositories>
  <repository>
    <id>github-unlaxer</id>
    <url>https://maven.pkg.github.com/opaopa6969/unlaxer-bom</url>
  </repository>
</repositories>
```

```xml
<!-- ~/.m2/settings.xml（コミットしない） -->
<settings>
  <servers>
    <server>
      <id>github-unlaxer</id>
      <username>あなたの GitHub ユーザー名</username>
      <password>${env.GH_PKG_TOKEN}</password>
    </server>
  </servers>
</settings>
```

```bash
GH_PKG_TOKEN=<read:packages トークン> mvn compile
```

`<password>` に実値を書かず `${env.GH_PKG_TOKEN}` にしておくと、トークンがディスクに残らない。
逆に、**この `<id>` を持つ `<server>` が既に settings.xml にあると、意図しないトークンが
送られることがある**（Maven は id の文字列一致だけで選ぶ）。

### 動作要件

| | 要件 | 根拠 |
|---|------|------|
| Java | **21 以上** | `pom.xml` の `<java.baseline>`。`unlaxer-common:3.0.11` の class file version が 65（= Java 21）。doma / flyway は 17 だが、トレイン全体の下限は 21 |
| Maven | 3.9 系で検証（BOM の import scope 自体は 3.x 全般で動く） | CI と開発環境 |

Java 21 未満だとどうなるかは、**どこで compile したか**で変わる（いずれも実測）。

- JDK 21 未満で **直接 compile** すると、その場で落ちる:
  `bad class file: ... class file has wrong version 65.0, should be 61.0`
- JDK 21 で compile したものを **JDK 21 未満で実行**すると、実行時にだけ落ちる:
  `UnsupportedClassVersionError: ... class file version 65.0 ... only recognizes ... up to 61.0`

危ないのは後者（build machine と実行環境が違う場合）。この下限は宣言値を信じるのではなく、
解決した jar の bytecode を実測して検証している（下記スクリプト）。

## 現在のトレイン: `2026.53`

| artifact | groupId | version | 備考 |
|----------|---------|---------|------|
| unlaxer-common | `org.unlaxer` | 3.0.11 | 全リポ共通基盤。**トレイン内で厳密統一を強制**する唯一の artifact |
| japanese-parser-common | `org.unlaxer` | 0.3.6 | 日本語住所テキスト処理共通（文字種/CodePoint モデル・正規化・tokenizer・translator 核）。onigiri / abr-utils が共有 |
| building-hierarchy | `org.unlaxer` | 0.19.4 | 住所→建物階層パーサー |
| abr-utils | `org.unlaxer.geo` | 0.10.12 | ABRUtils（住所検索本体・作法の基準） |
| onigiri-parser | `org.unlaxer` | 0.9.30 | onigiri 住所パーサー |
| historical-town-names | `org.unlaxer` | 0.1.0 | 歴史地名辞書（町名照合失敗時の字消費 fallback。onigiri 0.9.11 が利用） |
| municipality-history | `org.unlaxer` | 1.0.2 | 自治体統廃合履歴（historical-town-names の依存） |
| japanpost-history | `org.unlaxer` | 1.3.0 | 時系列郵便番号辞書（municipality-history 連携・PostcodeWithContext が利用。1.2.0 で差分方式、1.3.0 で diff 39 倍高速化） |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 | 検証済み 3rdパーティ（SQL/DAO） |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 | 検証済み 3rdパーティ（schema migration） |
| _jaddress-rdb-api_ | `org.unlaxer` | _（Phase 0 で枠予約済み・Phase 1 で新設予定）_ | rdb port（DAO interface + 永続 domain 型） |

過去トレインと検証エビデンスは **[CHANGELOG.md](CHANGELOG.md)** および **[history/](history/) ディレクトリ**（現在値は pom、履歴と根拠は doc の二層）。

## 運用ルール

- **現在値の真実は `pom.xml`**（機械可読・1トレインのみ）。**履歴と「なぜ/いつ/誰が検証したか」は CHANGELOG.md**。二重管理を避けるため各リポ README はここへ**リンクのみ**張る
- トレインを切る（新しい組み合わせを検証した）人が、`pom.xml` のバージョンを上げ、`CHANGELOG.md` に1ブロック追記する
- 中立リポ（どのエージェント/チームの縄張りでもない）。統合 PR を出した側が更新する

### consumer の明示 version drift を検査する

`scripts/check-bom-version-drift.py` は、この BOM が管理する座標について、consumer POM の
明示 version（通常依存と consumer 側の dependencyManagement）と BOM pin が異なれば失敗する。
consumer が BOM を import しているかどうかは問わない。
同じ version の明示指定と version 省略は許容する。

```bash
# unlaxer-bom と consumer を同じ workspace に clone して実行
python3 unlaxer-bom/scripts/check-bom-version-drift.py \
  --bom unlaxer-bom/pom.xml consumer/pom.xml consumer/module/pom.xml
```

意図的に BOM より先行する場合などは、該当する `dependency` 内に理由を残す。

```xml
<dependency>
  <groupId>org.unlaxer</groupId>
  <artifactId>japanese-parser-common</artifactId>
  <version>0.3.7</version>
  <!-- bom 例外: unlaxer-bom #123 に入るまでの先行検証 -->
</dependency>
```

この repo では同じ判定を次の3入口で使う。

- **Claude Code**: `.claude/settings.json` の PreToolUse hook。POM の Write/Edit を事前検査する
- **git**: `git config core.hooksPath .githooks` で pre-commit を有効化し、index 上の全 POM を検査する
- **手動 / CI**: 上記 CLI と `python3 -m unittest discover -s tests -v`

consumer repo へ展開するときも、判定を緩めた別実装を作らずこの checker を基準にする。
consumer の pre-commit / hook から使う場合は `--bom /path/to/unlaxer-bom/pom.xml` を渡せる。

### BOM の pin が実際に解決でき compile できるか検証する

`scripts/verify-bom-consumer-contract.py` は、BOM の**中核契約**を実行可能にする。

> **BOM の pin は、実際に解決でき、使える。**

BOM を隔離した Maven local repository に install し、それを `<scope>import</scope>` する
**最小 downstream consumer を実際に build** して確かめる（`~/.m2` は読まない・書かない）。

```bash
python3 scripts/verify-bom-consumer-contract.py
```

検証は 2 軸に分かれる。

1. **injection** — import した consumer に pin が注入されるか。第三者 artifact を1つも落とさずに
   **全座標**を検証する
2. **resolution + compile** — pin が実在して resolve でき、その jar に対して compile が通るか

**compile まで行うのは、version 文字列の比較では検出できない事故があるため。**
CHANGELOG `[2026.48]` の `unlaxer-common:2.8.0` は GitHub Packages と Maven Central に
同じ座標で中身違いで存在し、Central 側に `CodePointIndex.of` / `ZERO` が無かった。
resolve は成功して compile だけが落ちる型で、ここでだけ捕まる。

| exit | 意味 |
|------|------|
| 0 | 契約成立 |
| 1 | 契約違反（pin が注入されない / resolve・compile 失敗 / `bom registry` 宣言の不備 /
       BOM を読めない・pin の property を解決できない） |
| 2 | 確かめられなかった（Java・Maven 不在、Maven Central へ到達不可）。**環境の問題だけ** |

「壊れている」と「確かめられなかった」を混同しない。どちらも CI は失敗する。

#### `bom registry` 宣言

`pom.xml` の各 `dependency` には、その pin がどの registry から取れるかの宣言を置く。

```xml
<dependency>
  <groupId>org.unlaxer</groupId>
  <artifactId>unlaxer-common</artifactId>
  <version>${unlaxer-common.version}</version>
  <!-- bom registry: central -->
</dependency>
```

- `central` — Maven Central にある。**secret 不要**なので CI が常時 resolve + compile まで検証する
- `github` — GitHub Packages のみ。`read:packages` 認証が要るため、既定では
  **`UNVERIFIED` として座標ごとに列挙**する（黙って skip しない）

**宣言の無い座標があると検証は fatal で落ちる。** BOM に座標を足すときは必ず宣言すること。
現在の内訳（`central` 5 / `github` 7）はスクリプトの出力がそのまま表になる。

認証を持っている環境でなら、GitHub Packages 側も検証できる。トークンは引数では受け取らない。

```bash
GH_PKG_USER=<user> GH_PKG_TOKEN=<read:packages トークン> \
  python3 scripts/verify-bom-consumer-contract.py --include-github
```

#### release 前は `--require-all` で全座標を要求する

**PR の CI は secret を持たないため 12 座標中 5 座標しか resolve を確かめられない。**
GitHub Packages 側の pin が架空でも、その実行は「部分検証」として exit 0 になる。
出力は未検証座標を必ず列挙するが、**exit 0 を「全部確かめた」と読んではいけない**。

そのため release 時（`.github/workflows/publish.yml`）は deploy の前に
`--include-github --require-all` を通す。未検証が 1 つでも残れば exit 1 で publish しない。

```bash
GH_PKG_USER=<user> GH_PKG_TOKEN=<read:packages トークン> \
  python3 scripts/verify-bom-consumer-contract.py --include-github --require-all
```

#### この検証が保証しないこと

- **pin が「トレインとして意図した版」であること**は保証しない。実在して使えることまでしか見ない。
  `12.1.0` を `11.8.2` と打ち間違えても、その版が実在すれば通る。
  トレインの意図との突き合わせは現在 `CHANGELOG.md` / `history/` の人手レビューが担う（issue #10）
- **consumer が明示 version を書いたら BOM は負ける。** Maven の仕様で、明示指定は import した
  pin に無条件で勝ち、警告も出ない。これを防ぐのは `check-bom-version-drift.py` だけで、
  consumer repo 側で hook / CI に組み込まない限り機構としては何も強制されない
- **`java.baseline` は consumer に伝播しない。** import scope が運ぶのは dependencyManagement だけで
  property は運ばれない。consumer 側の `maven.compiler.release` が低くても Maven は何も言わない
  （依存 jar の bytecode 版数を見ないため）。ここで検証しているのは
  「BOM が固定した jar が、宣言した下限で動くか」であって consumer の設定ではない
- consumer repo の POM は見ない。それは `check-bom-version-drift.py` の担当

#### 第三者が採用するときの判断

`bom registry: github` の 7 座標（unlaxer 製品本体）は、**認証を持たない第三者には
resolve を再現できない**。PR の CI も secret を持たないため証明しない。
選べるのは次のどちらかで、どちらを取るかは採用側が明示的に決めること。

1. 自分で `read:packages` トークンを用意し、`--include-github --require-all` を自分でも回す
2. release 時の publish ワークフロー（deploy 前に `--require-all` を通す）の green を信頼材料として受け入れる

#### 2 つのスクリプトの exit code の違い

未解決 property のような「POM を読めない」系のエラーで、
`check-bom-version-drift.py` は **2**、`verify-bom-consumer-contract.py` は **1** を返す。
前者の 2 は Claude Code の PreToolUse hook で編集を止めるための値であり、意図的に変えていない。
両方を1つの自動化から呼ぶ場合は「非 0 なら失敗」で扱うこと。

#### 実行時の注意

- 作業用ディレクトリは `tempfile` 既定（`TMPDIR` があればそこ）に作られ、終了時に消える。
  **場所は生成した時点で stderr に出す**（強制終了されて後始末が走らなくても分かるように）。
  消せなかった場合も場所を出す
- **offline 挙動を試すときは `mvn -o` か `settings.xml` の `<proxy>` を使う。**
  `MAVEN_OPTS` の `-Dhttp.proxyHost` は Maven の resolver に効かず、
  「offline を試したつもりで実際は通信していた」という誤解を生む
- consumer 側で `<repository><id>github-unlaxer</id>` を書くと、Maven は同じ id を持つ
  `~/.m2/settings.xml` の `<server>` を**文字列一致だけ**で選び、そのトークンを送る。
  意図しない資格情報が使われないか確認すること。この検証スクリプト自身は
  毎回隔離した `settings.xml` を生成してこの経路を断っている

## 配置

Maven Central 未公開。ローカルでは `mvn install` で各 .m2 に配置:

```bash
mvn install   # → org.unlaxer:unlaxer-bom:2026.53 が .m2 に入る
```

publish の議論は onigiri-parser#78 を参照。

## Publishing（GitHub Packages）

```bash
# settings.xml（コミットしない）: server id=github-unlaxer / password=${env.GH_PKG_TOKEN}
GH_PKG_TOKEN=<write:packages トークン> mvn -s /path/to/settings.xml deploy
```

- リリース版は**同一バージョンの再 deploy 不可**（409 Conflict）。再公開はバージョンを上げる
- 注意（この環境）: gh v2.4.0 には `gh auth token` が無い。トークンは `~/.config/gh/hosts.yml` の `oauth_token`、
  またはスコープ `write:packages,read:packages` 付き PAT を使う

## リリース運用

リリースの仕組み・設定・運用（mermaid 付き）は [docs/RELEASE.md](docs/RELEASE.md) を参照。
