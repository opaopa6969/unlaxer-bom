# unlaxer-bom リリーストレイン履歴

各トレイン（CalVer `YYYY.MM`）の検証済みバージョンセットと、その**検証エビデンス**を記録する。
現在値の真実は `pom.xml`、本ファイルは過去全トレインと根拠を持つ（二層管理）。
新トレインは上に積む。

## [2026.08] - 2026-06-15

> 変更: onigiri-parser 0.8.0 → **0.9.0**（DD-008/009/010 ＋ building-hierarchy 統合 PR-A/B/C ＋ AUTO 既定）。他は据え置き。
> 目的: vacant-service 等の末端 consumer が BOM 経由で最新 onigiri を取り込めるようにする。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.1 |
| onigiri-parser | `org.unlaxer` | **0.9.0** |

### 検証・経緯
- onigiri-parser 0.9.0 = develop 2b97795（PR-C / AUTO 含む）。default 292 / with-bh 309 緑・CI 緑で検証。
- AUTO 既定: building-hierarchy が classpath にあれば建物名 +14pt（HEURISTIC 188 → UNLAXER 251 / 442件）、無ければ従来動作。
- ⚠️ registry publish（onigiri 0.9.0 / BOM 2026.08 を両 registry へ）は deploy token を持つリリースフロー側で実施。

## [2026.07] - 2026-06-14

> 変更: abr-utils 0.10.0 → **0.10.1**（ABRUtils#34 バグ1修正 a99b4ed を含む明示版）。他は据え置き。
> publish: opaopa6969（abr-utils は ABRUtils repo registry、他は unlaxer-bom registry）／caulis（全て unlaxer-bom registry）。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.1 |
| onigiri-parser | `org.unlaxer` | 0.8.0 |

### 検証・経緯
- abr-utils 0.10.1 = develop a99b4ed（#34 バグ1: 既定 codec を loadable に）を 0.10.0 と区別するため明示採番。
  「同一 0.10.0 に修正前/後が混在」問題を解消
- バグ2（mmap レイアウト不一致クラッシュ）は ABRUtils#35 で継続。snapshot データ版は v1.1.0-snapshot のまま
- ⚠️ 消費の注意（opaopa6969）: abr-utils は ABRUtils repo registry に居るため、利用側は
  `<repository>` を2つ（unlaxer-bom registry ＋ ABRUtils registry）必要。caulis は unlaxer-bom registry 1つで完結

---

## [2026.06] - 2026-06-13

> publish 状況（GitHub Packages, opaopa6969/unlaxer-bom registry）:
> 全 artifact publish 済み（GitHub Packages）:
> ✅ unlaxer-bom 2026.06 / ✅ building-hierarchy 0.14.1 / ✅ unlaxer-common 2.8.0 /
> ✅ onigiri-parser 0.8.0 ／ ✅ abr-utils 0.10.0（repo: ABRUtils 由来）
> ※ common/onigiri は deploy:deploy-file（.m2 由来）で投入。各リポ pom への distributionManagement 恒久化は次回リリース時
>
> **両 registry に publish 済み**（opaopa6969 と caulis、train 全 artifact）。
> caulis の CI/メンバーが opaopa6969 private packages を読めないケースに備えた完全ミラー。
> opaopa6969 を更新の正とし、caulis は同一版を deploy-file で複製する運用。


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
