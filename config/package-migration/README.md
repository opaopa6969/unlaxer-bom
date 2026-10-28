# 初回移行する公開済み成果物

`caulis/vacant-dev-workspace#19` の初回コピー用の座標一覧。
2026-10-29 に vacant-service develop `ac9e9dcb582aca3028068785fb54a598f6e86640`
を空の Maven キャッシュで依存解決し、`dependency:copy@copy-parser-jars` も実行して確認した。
この一覧は継続公開する版の指定には使わない。

| ファイル / caulis の公開先 | 座標数 | 内容 |
|---|---:|---|
| unlaxer-bom.json | 15 | BOM 2026.51 / 2026.56、本番と推移依存の各版、ライブラリ単体ビルド用の JPC 0.3.2 / japanpost-history |
| ikura-jaddress-parser.json | 9 | 0.4.2 の parent / core / dict-data、0.4.4 の全6モジュール |
| shake-jaddress-parser.json | 5 | 0.3.2 の parent / core / dict-data / api / cli |
| okaka-jaddress-parser.json | 1 | glm-jaddress-parser 0.1.1 |
| kombu-jaddress-parser.json | 1 | jaddress-parser 0.1.4 |

- ikura 0.4.4 の parent が BOM 2026.51 を import する。onigiri 0.9.32 の
  POM は building-hierarchy 0.19.1 と ikura 0.4.2 を参照するため、現在の勝者の版だけでは足りない。
- historical-town-names 0.1.0 の推移依存として JPC 0.1.0 と municipality-history 1.0.1 も含める。
- unlaxer-common **3.0.11 は Maven Central の成果物**を使う。古い GitHub 版 2.8.0 と混同しない。
- jar / sources / javadoc は公開元と同一バイト列。POM の Maven registry URL のみ
  caulis 向けに変換し、元 POM とその SHA-256 を別途保存する。
- municipality-history **1.0.0 は元 registry の metadata に存在せず、POM も 404**
  （Maven Central も 404）。古い caulis/japanpost-history main はこの版を optional 依存に指定している。
  一覧から欠落した版として扱い、別の HEAD から同じ版を作り直さない。
  本番の BOM では 1.0.2 が使われるが、japanpost-history のソース同期・依存更新は別途必要。
- abr-api / abr-historical / kugiri は現状 `0.1.0-SNAPSHOT`。固定された既存 release を
  コピーする本スクリプトの対象外。caulis のソースから継続公開する経路を別途整える。

この一覧の作成は移行完了を意味しない。caulis 側への公開、管理アカウントによる読み取り、
各ライブラリの継続公開、vacant-service の取得先変更とクリーンビルドは親 issue の残作業。


## municipality-history 1.0.0 の互換性注意

ソースから補完した1.0.0は japanpost-history の同梱版と fullName() の公開範囲が異なります。[補完記録の追補](../../docs/municipality-history-1.0.0-bootstrap.md)を参照し、japanpost-history のビルドには既存1.0.2を使用してください。
