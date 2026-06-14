# unlaxer-bom

unlaxer プロジェクト群の **検証済みバージョンセット（Bill of Materials）**。
各リポは独立 SemVer のまま、**BOM のバージョン（CalVer `YYYY.MM`）だけがリリーストレイン番号**になる
（Jackson / Spring と同方式）。

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
      <version>2026.06</version>
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

## 現在のトレイン: `2026.06`

| artifact | groupId | version | 備考 |
|----------|---------|---------|------|
| unlaxer-common | `org.unlaxer` | 2.8.0 | 全リポ共通基盤。**トレイン内で厳密統一を強制**する唯一の artifact |
| building-hierarchy | `org.unlaxer` | 0.14.1 | 住所→建物階層パーサー |
| abr-utils | `org.unlaxer.geo` | 0.10.0 | ABRUtils（住所検索本体・作法の基準） |
| onigiri-parser | `org.unlaxer` | 0.8.0 | onigiri 住所パーサー |

過去トレインと検証エビデンスは **[CHANGELOG.md](CHANGELOG.md)**（現在値はこの pom、履歴と根拠は doc の二層）。

## 運用ルール

- **現在値の真実は `pom.xml`**（機械可読・1トレインのみ）。**履歴と「なぜ/いつ/誰が検証したか」は CHANGELOG.md**。二重管理を避けるため各リポ README はここへ**リンクのみ**張る
- トレインを切る（新しい組み合わせを検証した）人が、`pom.xml` のバージョンを上げ、`CHANGELOG.md` に1ブロック追記する
- 中立リポ（どのエージェント/チームの縄張りでもない）。統合 PR を出した側が更新する

## 配置

Maven Central 未公開。ローカルでは `mvn install` で各 .m2 に配置:

```bash
mvn install   # → org.unlaxer:unlaxer-bom:2026.06 が .m2 に入る
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
