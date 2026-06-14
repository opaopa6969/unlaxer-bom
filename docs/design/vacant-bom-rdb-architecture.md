# 設計: 製品ライン対応 BOM + rdb の port 分離

> ステータス: **設計確定・未実装**(2026-06-15)
> 中立リポ(unlaxer-bom)に置く製品横断の設計ドキュメント。実装は本ドキュメントの段階プランに従う。

## 1. 目的 / 背景

unlaxer-bom を「onigiri-parser の BOM」ではなく **「vacant 製品の BOM」** として捉え直す。さらに将来、
onigiri-parser を vacant 以外の製品(例: address-normalize)でも使い回せるようにする布石を打つ。

将来像(依存トポロジ):

```
              onigiri-parser (共有・純粋パーサ)
             ╱                    ╲
    vacant-rdb                address-normalize-rdb
        │                            │
  vacant-service            address-normalize-service
```

狙い: **製品ラインごとに {共有 parser + 専用 rdb + service} の「検証済み組合せ」を BOM で固定する**。
例: `onigiri-parser vX.X.X` と `vacant-service vY.Y.Y` は `vacant-rdb vR.R.R` を使う、を BOM が宣言する。

## 2. 核心課題と解(ports & adapters)

同じ onigiri-parser が `vacant-rdb` と `address-normalize-rdb` の両方で使われる以上、
**parser が具体 rdb に直接依存していてはならない**。現状は逆で、onigiri-parser が entity/dao を内蔵し
`parser → dao` が 136 本ある。

→ **依存性逆転(ports & adapters)で解く**:

- `onigiri-parser` は **rdb の port(DAO interface + 永続 domain 型)にだけ依存**する
- `vacant-rdb` / `address-normalize-rdb` はその port の **具象実装**(entity / dao / Doma SQL / Flyway / schema)
- どの実装をどのバージョンで使うかは **製品 BOM が固定**

## 3. 目標アーキテクチャ(artifact 構成)

| 層 | artifact | 役割 | 依存 |
|----|----------|------|------|
| 基盤 | `unlaxer-common` | 共通ユーティリティ(既存) | — |
| **port** | `jaddress-rdb-api`(新) | DAO interface + 永続用 domain 型。実装非依存 | common |
| パーサ | `onigiri-parser` | 純粋パーサ。**rdb-api(port)のみ依存** | common, rdb-api, building-hierarchy, abr-utils |
| **rdb 実装** | `vacant-rdb` / `address-normalize-rdb` | port 具象(entity / dao / Doma SQL / Flyway / schema) | common, rdb-api, doma, flyway |
| service | `vacant-service` / `address-normalize-service` | 具象 rdb + parser を結線 | 対応 rdb, parser |

## 4. BOM の2層化

| BOM | 役割 | 固定する artifact |
|-----|------|------------------|
| `unlaxer-bom`(共通) | 全製品で共有する検証済み版 | unlaxer-common / onigiri-parser / building-hierarchy / abr-utils / **jaddress-rdb-api** / doma 3.6.0 / flyway 12.1.0 |
| `vacant-bom`(製品) | vacant 製品の組合せ | 共通 BOM を import + `vacant-rdb` + `vacant-service` |
| `address-normalize-bom`(将来) | 同型 | 共通 BOM を import + `address-normalize-rdb` + `address-normalize-service` |

> これにより前段の「BOM に doma/flyway を入れる」が正当化される — 各 rdb 実装が doma/flyway バージョンを
> BOM 経由で必ず揃えられ、drift を防げる(Spring Boot BOM と同方式)。

## 5. 最大の障害: 循環依存

port 分離の前提は **entity ↔ model ↔ parser の循環を断つこと**(onigiri-parser での実測):

| 方向 | 件数 | 判定 |
|------|------|------|
| entity/dao → model | 131 | **上向き逆参照(諸悪の根源)** |
| entity/dao → parser | 9 | **上向き逆参照** |
| model → entity | 38 | 循環(下向き正常だが entity↔model は相互依存) |
| parser → entity/dao | 136 | 下向き(正常) |

port 化 = entity/dao が model/parser を **見ない** 状態を作ること。domain 型を `jaddress-rdb-api` 側へ
中立化して移すのが Phase 1 の本体工事。

## 6. 現状の事実(2026-06-15 時点)

- スキーマは2系統:
  - onigiri-parser → `db/migration/parser/`(住所辞書・ken_all 系 = parser スキーマ)
  - vacant-service → `db/migration/caulis/`(service運用 / auth / verification_result 系 = caulis スキーマ)
- vacant-service は onigiri-parser を `modules/onigiri-parser` としてベンダリング(ビルド済み jar + sources)。
  起動時に parser + caulis の両 migration を**同一 PostgreSQL** に流す。
- 両リポとも **Doma 3.6.0 + Flyway 12.1.0**。

## 6.1 履歴 / 前例(prior art)

かつてデータアクセス層は独立リポ(`vacant-data-access`、※社内 confidential)として**分離されていた**前例がある。
これが **allinone 化(vacant-allinone への統合)で取り込まれ**、entity/dao が model/parser と絡んで循環が生まれた
と考えられる。今回の vacant-rdb は「once 分離されていた境界を port 分離の形で再分離する」位置づけ
= **クリーンな分離は過去に実在しており実現可能**(詳細は当該リポを参考程度に参照)。

**現状の継ぎ目**: `org.unlaxer.jaddress.parser.DataSourceContainer` が DataSource をパーサへ渡している。
port 化ではこの継ぎ目を `jaddress-rdb-api` 側の正式な境界に昇格させるのが自然。

## 7. 段階プラン

| Phase | 内容 | 前提/リスク |
|-------|------|------------|
| **0** | `unlaxer-bom` を共通 BOM として再定義(README / 役割)。doma 3.6.0・flyway 12.1.0 を dependencyManagement に追加。`jaddress-rdb-api` の枠を予約 | なし・低リスク |
| **1** | `jaddress-rdb-api` 新設。DAO interface と永続 domain 型を抽出し、**entity/dao → model/parser の上向き参照を切断** | 本体工事(循環断ち) |
| **2** | `vacant-rdb` を独立 jar 化(parser schema の entity / dao / Doma SQL / Flyway)。onigiri-parser を port のみ依存に。vacant-service が vacant-rdb を結線 | Phase 1 完了が前提 |
| **3** | `vacant-bom` を新設(共通 BOM import + vacant-rdb / vacant-service 固定)。opaopa6969 / caulis 両 remote へ publish | Phase 2 完了が前提 |
| **4(将来)** | `address-normalize-rdb` / `-service` / `-bom` を Phase 2-3 と同型で追加 | 布石の回収 |

## 8. 決定事項(本設計で確定済み)

- rdb 抽象度 = **ports & adapters(本格)** を採用(「同一 rdb のバージョン違い」案は不採用)
- BOM 構造 = **2層(共通 + 製品)** を採用(単一 BOM 案は不採用)

## 9. CI/CD・GitHub Actions

### 9.1 現状(調査結果 2026-06-15)

| repo | ci | publish | publish 先 | 備考 |
|------|----|---------|-----------|------|
| onigiri-parser | ci.yml(auth-free 既定ビルド、DB テストは surefire で除外、with-bh/with-abr は profile 隔離 #77)+ test.yml | publish.yml(`release: published` / 手動) | **GitHub Packages**(PAT `PACKAGES_PUBLISH_TOKEN`、settings.xml に `github-unlaxer-bom` / `github-abrutils`) | `-Pwith-bh,with-abr -DskipTests deploy` |
| ABRUtils | ci.yml | publish.yml | **Nexus**(`nexus-unlaxer-releases`、`NEXUS_USER`/`NEXUS_TOKEN`) | ← GitHub Packages と不一致 |
| building-hierarchy | ci.yml のみ | **なし** | ?(onigiri の with-bh 同梱 or 手動) | publish 経路が不明瞭 |
| unlaxer-bom | **なし** | **なし** | 手動(`mvn -s settings.xml deploy`) | BOM リリースが属人的 |
| vacant-service | ci.yml | deploy-ecr.yml | AWS ECR | service デプロイ(成果物配布ではない) |

### 9.2 設計上の問題点

1. **publish 先の分裂**: ABRUtils=Nexus、onigiri=GitHub Packages。BOM README が掲げる「単一ホスト方式(unlaxer-bom registry に集約)」に反する。**GitHub Packages に統一すべき**。
2. **unlaxer-bom / building-hierarchy に publish workflow が無い**: BOM 本体と bh のリリースが手作業・属人的。CI 化が必要。
3. **auth-free CI の前提が崩れる**: 現在 onigiri-parser の既定ビルドは private registry 不要(#77)。だが rdb-api を **onigiri-parser の必須依存**にすると、既定 CI が registry 認証(read:packages)を要求するようになる。対処案 → (a) rdb-api を Maven Central 公開 / (b) CI に read:packages 付与 / (c) profile 隔離。**要判断**。

### 9.3 新アーキでの CI/CD 方針

- **共通テンプレート**: 各 artifact に `ci.yml`(auth-free な compile/test)+ `publish.yml`(`release: published` → PAT で **GitHub Packages へ deploy、単一ホストに統一**)。
- **`jaddress-rdb-api`**: leaf(common のみ依存・DB 不要)。ci.yml + publish.yml は最小構成で済む。
- **`vacant-rdb`**: ci.yml で **PostgreSQL service container** を起動し Flyway/Doma の DB テストを実行 + publish.yml。rdb-api を registry から read。
- **`unlaxer-bom` / `vacant-bom`**: pom-only。ci.yml(`mvn validate` / effective-pom 検証)+ publish.yml(`release` → `deploy`)を**新設**(Phase 0 で着手)。
- **onigiri-parser publish.yml**: rdb-api 依存化に伴い settings.xml server に rdb-api registry を追加。port 化後は with-bh/with-abr 同梱ロジックを簡素化できる余地。
- **リリース協調**: 2層 BOM は「製品リリース = 複数 artifact の release 連動」。publish は GitHub release トリガなので、タグ規約(既存 `v{YYMMDDHHmmss}`)で artifact 群の release をまとめる運用を定義する。

> なお publish はローカル環境ではなく CI(secrets 保持)が実行する設計のため、ローカルに settings.xml / PAT が無くても publish は CI 経由で成立する。
