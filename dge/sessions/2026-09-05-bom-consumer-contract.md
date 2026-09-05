# DGE セッション 2026-09-05 — unlaxer-bom の製品価値Gap探索

- 対象 repo: `unlaxer-bom`（main = `9f581fb`、open PR なし、open issue は epic #1 のみ）
- 手法: DGE（Design-Gap Exploration）。利用者証言 → 専門家反論 → 設計判断 → Gap の順で回す
- 実行環境: OpenJDK 21.0.2 / Apache Maven 3.9.9（wrapper・container 代替は不要だった）
- 事実確認はすべて**この repo の実物に対する実測**で取った（引用箇所に実測値を併記）

## 登場人物

| 役 | 名 | 立場 |
|----|----|------|
| 単純化役 | 削ぎ落とし | 「増やす前に削れないか」。新スクリプトに反対する |
| 前提を疑う役 | 反証 | 「その保証は本当に効いているのか」を実測で潰す |
| 実利用者 | 初見の採用者 | vacant 製品群を初めて触る。README だけが頼り |
| 運用者 | トレイン担当 | 月に数回トレインを切って release する |
| テーマ専門家 | BOM 設計者 | Jackson/Spring 方式の BOM 運用と Maven の解決規則に詳しい |

---

## 第1幕 — 主担当の初期案「docs が pom から drift する」

**主担当**: 一番わかりやすい穴は docs の drift だ。issue #6 が実際にそれで、
2026.50〜2026.53 の 4 トレイン分、README 表・CHANGELOG・history/ が pom から遅れていた。
README は「現在値の真実は `pom.xml`」と宣言しておきながら、README 表自身が全 version を複写している。
機械的な照合が無い。

**運用者**: 痛みは本物だ。手で直した（PR #7）。ただ、あれは**気づけた**。
表が古いと気づいた人がいて、issue になって、直った。俺が本当に怖いのはそこじゃない。

---

## 第2幕 — 実利用者の証言「green だったのに、下流で壊れた」

**初見の採用者**: 私が知りたいのは1つだけです。
「README に書いてあるこの組み合わせを import したら、本当にその版が入って、動くのか」。
BOM の存在理由はそこですよね。docs が1トレイン遅れているのは、正直、読めば気づきます。
気づけないのは、**pom に書いてある版がそもそも取れない**ときです。

**トレイン担当**: それは CI が見ている。`mvn -B -N validate` で
「pom の妥当性 + dependencyManagement の解決可否を検証する」と `.github/workflows/ci.yml` に書いてある。

**反証**: それは書いてあるだけだ。実測する。

```
# pom.xml の building-hierarchy を 0.19.4 → 0.19.5（未 publish の架空版）に差し替え
$ mvn -B -N validate            → BUILD SUCCESS  (exit=0)
$ python3 scripts/check-bom-version-drift.py --bom pom.xml pom.xml → exit=0
```

**現行 CI の 2 ゲートは、両方とも素通しした。**
`mvn -N validate` は非再帰の model 検証で、dependencyManagement の**解決は一切行わない**。
drift checker は consumer POM の明示 version と BOM pin の**文字列比較**であって、
pin 自身が実在するかは見ていない（設計どおり。責務が違う）。

**BOM 設計者**: つまり、ci.yml のコメントは実装と乖離している。
「解決可否を検証する」という記述に、対応する実装が無い。

---

## 第3幕 — 反論役の一撃「version が実在しても足りない」

**反証**: もっと悪い話をする。この repo の**創業事故**は version の取り違えではない。
README 冒頭と CHANGELOG `[2026.48]` にこうある —
`org.unlaxer:unlaxer-common:2.8.0` が **GitHub Packages と Maven Central の両方に、同じ座標で中身違いで存在していた**。
Central 側には `CodePointIndex.of` / `ZERO` が無く、japanese-parser-common の CI が
`cannot find symbol` で全滅した。

**座標が同じで中身が違う。version 文字列の照合では原理的に検出できない。**
検出できるのは、**解決された jar に対して実際に compile したとき**だけだ。

実測（Central から取得した `unlaxer-common:3.0.11` の jar を javap）:

```
public class org.unlaxer.CodePointIndex extends org.unlaxer.base.IntegerValue<...> {
  public static final org.unlaxer.CodePointIndex ZERO;
  public static org.unlaxer.CodePointIndex of(int);
```

3.0.11 には在る。壊れた「2.8.0」には無かった。
**この repo は、自分が生まれる原因になった事故を、いまだに機械的に検出できない。**

---

## 第4幕 — 運用者の一撃「そもそも全部は取れない」

**トレイン担当**: 実装しようとすると現実にぶつかるぞ。うちの artifact は Maven Central に無い。
GitHub Packages 単一ホスト方式だ（onigiri-parser#78）。CI で全部解決させたら secret が要る。

**実測**（BOM が管理する 12 座標に対し、Maven Central へ直接 HTTP）:

| 座標 | Central | 
|------|---------|
| `org.unlaxer:unlaxer-common:3.0.11` | **200** |
| `org.seasar.doma:doma-core:3.6.0` | **200** |
| `org.seasar.doma:doma-processor:3.6.0` | **200** |
| `org.flywaydb:flyway-core:12.1.0` | **200** |
| `org.flywaydb:flyway-database-postgresql:12.1.0` | **200** |
| `org.unlaxer:japanese-parser-common:0.3.6` | 404 |
| `org.unlaxer:building-hierarchy:0.19.4` | 404 |
| `org.unlaxer.geo:abr-utils:0.10.12` | 404 |
| `org.unlaxer:onigiri-parser:0.9.30` | 404 |
| `org.unlaxer:historical-town-names:0.1.0` | 404 |
| `org.unlaxer:municipality-history:1.0.2` | 404 |
| `org.unlaxer:japanpost-history:1.3.0` | 404 |

**12 座標中 5 つは secret 無しで検証できる。7 つは GitHub Packages の認証が要る。**

**初見の採用者**: ……その表、私が一番欲しかったものです。
README の使い方 snippet をそのまま貼ったら、`unlaxer-common` は取れて `building-hierarchy` は 404 になる。
どれが public でどれが認証要りなのか、いまは README のどこにも書いていない。

**BOM 設計者**: では検証は **2 軸**に分ける。混ぜるから「できない」になる。

1. **injection 契約** — BOM を import した consumer に、pin が実際に注入されるか。
   これは Maven の model 解決だけで済み、**第三者 artifact を1つも落とさずに全 12 座標を検証できる**。
2. **resolution + compile 契約** — pin が実在し、resolve でき、compile が通るか。
   これは registry と認証に依存する。**public な 5 座標は secret 無しで CI で常時検証できる。**

**削ぎ落とし**: 7 座標が未検証で残るなら、この仕組みは嘘をつくことにならないか。

**BOM 設計者**: 嘘になるのは**黙って skip したとき**だけだ。
「認証が無いので未検証」と**明示的に出力する**なら、それは正確な報告だ。
そして未検証の 7 件を列挙した出力は、そのまま第4幕で採用者が欲しがった表になる。

---

## 第5幕 — 対立の解き方（cross-persona-conflict）

**削ぎ落とし**: 既存の `check-bom-version-drift.py` に相乗りできないのか。原語を増やすな。

**BOM 設計者**: 責務が違う。既存は「BOM を真実とし、**consumer の書き方**を静的に正す」。
今回は「**BOM の pin 自身**が下流で成立するかを、実際に Maven を回して確かめる」。
静的テキスト検査と実 build は、実行時間も失敗モードも別物だ。1つに混ぜると `--hook` が Maven を起動しかねない。

ただし **BOM の読み取りは共有する**。managed 座標の抽出は既存の `managed_versions()` を import して使う。
README の既存方針「判定を緩めた別実装を作らずこの checker を基準にする」に従う。
増える原語は**1つだけ**: 「**pin は、実際に解決でき、使える**」。

**削ぎ落とし**: それなら通す。「増やす前に削れないか」の答えは
「削るのではなく、既に宣言だけされていた保証に実装を与える」だ。ci.yml のコメントが先に存在していた。

**運用者**: registry の public/private をどう持つ。二重管理は御免だ。

**BOM 設計者**: pom.xml が「現在値の真実」なのだから、そこに置く。
既存の `<!-- bom 例外: 理由 -->` と同じ形で `<!-- bom registry: central|github -->` を pin の隣に置く。
**未宣言は fatal** にする。新しい座標を足す人に「これはどこから取れるのか」を必ず答えさせる。

---

## 第6幕 — Gap 一覧

| # | Gap | O/S/A | Category | Severity | 採否 |
|---|-----|-------|----------|----------|------|
| GAP-01 | BOM の中核契約（import すれば pin が注入され、実在し、compile できる）に実行可能な証明が無い。ci.yml は「解決可否を検証する」と書くが実装が無い。存在しない pin が両ゲートを素通しする（実測 exit=0/0） | Act | correctness / release-safety | **high** | **採用** |
| GAP-02 | 同一座標・中身違いの artifact（創業事故 2.8.0）を検出する手段が無い。version 照合では原理的に不可能 | Act | correctness | **high** | **採用**（GAP-01 に含める。compile 契約がこれを担う） |
| GAP-03 | どの座標が Central で取れ、どれが GitHub Packages 認証を要するかが README のどこにも無い（実測 5/12 が public） | Act | onboarding | medium | **採用**（GAP-01 の出力と pom の registry 宣言で解消。README への網羅的な GH Packages 設定手順は保留） |
| GAP-04 | README 表 / CHANGELOG / history が pom から silently drift する（issue #6 = 4 トレイン分の実績、PR #7 で手作業修正） | Act | docs-integrity | medium | **保留** — 独立した slice。GAP-01 と混ぜると PR が2つの原語を持つ |
| GAP-05 | consumer 向けの GitHub Packages `<repositories>` + `read:packages` 設定手順が README に無い（CHANGELOG 2026.48 に secret 欠如で CI 全落ちの実例） | Suggest | onboarding | medium | **保留** — GAP-04 と同じ docs slice で扱うのが自然 |
| GAP-06 | 「unlaxer-common はトレイン内で厳密統一を強制する唯一の artifact」と README/pom が言うが、強制する実装は無い（drift checker は全座標を同等に扱う） | Observe | docs-integrity | low | **却下** — 実害の証拠が無い。文言側を直すべきで、機構を足す話ではない |
| GAP-07 | epic #1 Phase 1（`jaddress-rdb-api` 新設）が未着手 | Act | architecture | high | **却下** — 別 repo の新設が必要で、この repo 単独では完結しない。epic #1 が追跡済み。**GAP-01 とは無関係で重複しない** |

### 採用: GAP-01（GAP-02 / GAP-03 を内包）

理由: BOM という製品の存在価値そのもの（「この組み合わせは検証済み」）に対する、
唯一の実行可能な証明が欠けている。しかも欠けていることが ci.yml のコメントによって
**隠されている**（読んだ人は検証済みだと思う）。さらに、検出できていない事故の型が、
この repo が作られた原因そのものである。

---

## 第7幕 — tramli / tramli-appspec 適合性評価

5 軸で評価する（判定軸は既存 DGE セッション群の運用に合わせた）。

| 判定軸 | 要否 | 理由 |
|--------|------|------|
| human-in-the-loop（途中で人間の承認が挟まる） | × | 検証は同期実行。green/red のみ |
| 長期状態（プロセスを跨いで永続する state） | × | 各実行は隔離した local repository で完結し、実行間に状態を持たない（決定性の要件そのもの） |
| 補償（失敗時の巻き戻し処理） | × | 副作用は temp ディレクトリのみ。削除で済む |
| 外部 event（外部からの再開契機） | × | 契機は CI / 手動実行のみ |
| requires-produces 契約（DataFlowGraph で検証する価値） | × | 段は install → effective-pom → compile の直列 3 段。関数合成で足りる |

**5 軸すべて × → 不採用。** tramli の README 自身が
「外部 event が無いなら Pipeline すら推奨しない」「2〜4 段の直列は関数合成」と述べており、
ここで導入すれば「抽象化のためだけの導入」になり minimal primitives / YAGNI に反する。

なお `tramli-appspec` の skill は `applies_when: repo.has_file: pom.xml` で gate されるため
この repo に**マッチしてしまう**が、これはファイル名レベルの一致であって構造的な適合ではない。
unlaxer-bom は `src/` を持たない pom-only repo であり、flow も entity も role も存在しない。

**再検討条件**: BOM の検証が「複数 registry への publish → 外部の下流 repo での検証 →
結果を待って promote」のような、**外部 event を待つ長時間フロー**になったとき。
epic #1 Phase 3（`vacant-bom` 新設・両 remote へ publish）がその形に近づく可能性があり、
そこで再評価する。

---

## 結論

GAP-01 を採用し、`scripts/verify-bom-consumer-contract.py` として
「**BOM の pin は、実際に解決でき、使える**」という原語を1つ追加する。
GAP-04 / GAP-05 は docs 整合の独立 slice として保留し、本 PR では扱わない。
tramli / tramli-appspec は不採用。
