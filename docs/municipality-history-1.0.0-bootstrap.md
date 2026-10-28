# municipality-history 1.0.0 のソースからの補完

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
