# municipality-history 1.0.0 のソースからの補完

> 互換性の追補: この source-build 1.0.0 は、japanpost-history に同梱されていた1.0.0と公開 API が一致しない。`MunicipalityChange.fullName()` が package-private のため、japanpost-history のビルドには使用しない。利用側は既存の1.0.2へ進める（caulis/japanpost-history#43）。以下は当時の公開・検証記録であり、その依存の互換性確認完了を意味しない。

japanpost-history がビルド時の optional 依存に指定する `org.unlaxer:municipality-history:1.0.0` は、
元の GitHub Packages と Maven Central では404だった。一方、caulis の Git 履歴にその版のソースが残っていた。
既存の公開済み jar をコピーした初回31座標とは区別し、この1座標は当時のソースから生成した。
現在のアプリが使う1.0.1 / 1.0.2の pin は変更していない。

- source: [caulis/municipality-history の0b3c77a](https://github.com/caulis/municipality-history/tree/0b3c77aba36555d7d54f5ae14d5abd7a9cb984ab)
- source commit: `0b3c77aba36555d7d54f5ae14d5abd7a9cb984ab`（caulis main の祖先）
- POM 宣言: `org.unlaxer:municipality-history:1.0.0`
- source / POM の編集: なし
- build: JDK21.0.9、空の Maven cache、`mvn -B -ntp -Dgpg.skip=true clean verify`
- build 結果: 成功。この当時のソースに unittest はない。
- 実行確認: 生成 jar の `MunicipalityHistory.loadBundled()` が3,507件を読み、`findByName("浦和")` が5件を返す。

新しい HEAD で古い版を作らず、由来が追える当時のソースから生成する方法を選んだ。
コード・CSV・依存の版は変更していない。元 registry から取得した jar との同一性は主張しない。
公開済み jar の SHA-256 とビルド環境を記録し、再実行にはその同じ bundle を使う。

## 公開記録

- private draft Release: `maven-bootstrap-2026-10-29-2`（draft のまま保持）
- bundle SHA-256: `2993b6d76c7d7e6c07f8f77a8493461aecaef60a7db78b24e85aa79f2313fd90`
- [初回公開](https://github.com/caulis/unlaxer-bom/actions/runs/40745191612): 成功
- [再実行](https://github.com/caulis/unlaxer-bom/actions/runs/40745526129): 新規0・同一1、再公開なしで成功
- 認証: caulis/unlaxer-bom の `GITHUB_TOKEN` のみ
- 公開ファイル: POM / jar / sources.jar / javadoc.jar。公開後に全ファイルのハッシュを再照合。

draft Release に `maven-bootstrap.zip`、`maven-bootstrap.json`、source archive、
`municipality-1.0.0-provenance.json`、build / probe log を保存した。
manifest の `sourceKind=built-from-git`、`sourceCommit`、`buildCommand` で
Maven registry からの既存 jar のコピーと区別できる。

同じ入力を [bootstrap workflow](maven-package-bootstrap.md) に渡すと、
既存ファイルとの一致を確認して公開をスキップする。不一致や部分公開時は書き込み前に停止する。
この操作は通常の継続公開や、別 repo に対する管理 Secret の Read 検証を代替しない。
親 caulis/vacant-dev-workspace#19 はそれらの完了まで OPEN のままとする。

## 公開 API の不一致と利用側の修正

後から [japanpost-history に同梱された jar](https://github.com/caulis/japanpost-history/blob/2141149cc3d0b23d450eec705e2657683f73f15f/local-repo/municipality-history-1.0.0.jar) と照合したところ、data と他のクラスは同一だったが、`MunicipalityChange.class` に差があった。`javap -p -c` の比較では `fullName()` の公開範囲が異なり、ソース履歴にはその後の public 化 commit `250d7de` が存在する。

| 比較対象 | jar SHA-256 | fullName() |
|---|---|---|
| japanpost-history の同梱1.0.0 | `3a0de0b2918d676561a8f0a986a5f9f0c7dfa71d1c8c5be8558f5080982b0c45` | public |
| 今回の source-build 1.0.0 | `81fb7883478f2d5b4ba86e2e143d2113109a4105535975b9626bfa4b0bee5b45` | package-private |

当時の loadBundled / findByName の probe だけでは、この差を検出できなかった。実際に japanpost-history の clean compile で source-build 1.0.0を選ぶと `fullName() is not public` で失敗することを確認した。公開 API のある既存1.0.2を選ぶと clean verify は128テスト・失敗0・skip0で成功した。

既存 release 座標の削除・置換は行わない。japanpost-history の次版1.3.1は1.0.2に依存し、caulis 設定では caulis Packages から取得する。個人側 CI は公開1.0.2ソースの固定 commit をビルドする。既存の1.3.0を再公開せず、現行 vacant-service の明示 pin（1.0.2）も維持する。

registry metadata の latest は1.0.2だった。1.0.0を最新として推奨したり、同梱版と同一の ABI と扱ったりしない。source-build 版の公開記録と元 bundle は履歴として保持する。

今後、取得できない旧版をソースから補完する場合は、POM の version だけで source commit を決めない。既存 repo の同梱成果物・タグ・公開 API を照合し、実 consumer の clean compile / test まで検証してから公開する。
