# unlaxer-bom リリーストレイン履歴

各トレイン（CalVer `YYYY.MM`）の検証済みバージョンセットと、その**検証エビデンス**を記録する。
現在値の真実は `pom.xml`、本ファイルは過去全トレインと根拠を持つ（二層管理）。
新トレインは上に積む。

## [2026.06] - 2026-06-13

> publish 状況（GitHub Packages, opaopa6969/unlaxer-bom registry）:
> ✅ unlaxer-bom 2026.06 / ✅ building-hierarchy 0.14.1 / ✅ abr-utils 0.10.0（既存）
> ⏳ unlaxer-common 2.8.0・onigiri-parser 0.8.0 は未 publish


| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.0 |
| onigiri-parser | `org.unlaxer` | 0.8.0 |

### 検証
- onigiri-parser develop（`7b23c41`、#74 マージ済み）＋ building-hierarchy 0.14.0 で
  **全298テスト green**（onigiri-parser PR #76 = building-hierarchy 統合 PR-A）
- building-hierarchy 0.14.1 単体: 全255テスト green、gold-standard 検出率 96.8%
- unlaxer-common は onigiri develop / main とも 2.8.0 で統一

### 初収録の経緯
- 初トレイン。BOM 方式の採用は onigiri-parser#78
- このトレインで building-hierarchy を初収録（onigiri 統合 PR-A）
- ⚠️ 取り違え注意: 計画初期に unlaxer-common を 1.1.26 と誤認（古い `vacant-allinone-for-reference` を見ていた）。
  実リポは 2.8.0。**バージョン確認は必ず実リポの pom を正とすること**

### 既知の注意
- いずれの artifact も Maven Central 未公開。ローカル `mvn install` 前提
  （building-hierarchy は `mvn install -DskipTests -Dgpg.skip=true`）
- abr-utils の groupId は `org.unlaxer.geo`（他は `org.unlaxer`）
