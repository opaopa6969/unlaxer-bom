# unlaxer-bom

運用ルールは README.md の「運用ルール」を正とする。ここには、README だけでは見落としやすい点を書く。

## 外部ライブラリの版を固定したら、consumer の pom にも同じ版を書く

- doma / flyway / tools.jackson のような外部ライブラリ（`org.unlaxer` 以外）の版をこの BOM で固定・変更したら、
  vacant-service の `service/pom.xml` にも同じ版を書く（properties や Maven Central の BOM の import で）。
- 理由: この BOM は GitHub Packages で配布していて認証が必要なため、Snyk の Web 画面（GitHub 連携）は取得できない。
  BOM の中だけで固定した版は Snyk の Web 画面では効かず、固定前の版（推移的依存が持ち込む版）で判定される。
  2026.58 で tools.jackson を 3.1.8 に固定したとき、vacant-service の Snyk に flyway 経由の critical 3 件が残った（vacant-service #347）。
- 今の対応: doma = `doma.version`、flyway = `flyway.version`、tools.jackson = `tools.jackson:jackson-bom` の import。
- `scripts/check-bom-version-drift.py` は同じ座標の明示 version しか比べない。vacant-service は tools.jackson を
  `tools.jackson:jackson-bom`（BOM が管理していない座標）で固定しているので、`tools-jackson.version` を上げても
  drift として検出されない。上げるときは vacant-service 側を手で合わせる。
