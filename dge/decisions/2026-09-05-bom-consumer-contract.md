# 設計判断 — BOM の pin に「実際に解決でき、使える」証明を与える（GAP-01）

- 日付: 2026-09-05
- 由来: [dge/sessions/2026-09-05-bom-consumer-contract.md](../sessions/2026-09-05-bom-consumer-contract.md)
- 実装仕様: [dge/specs/2026-09-05-bom-consumer-contract.md](../specs/2026-09-05-bom-consumer-contract.md)
- issue: #9
- 状態: **採用（実装対象）**

## 決めたこと

`scripts/verify-bom-consumer-contract.py` を追加し、原語を **1 つだけ**増やす:

> **BOM の pin は、実際に解決でき、使える。**

検証は 2 軸に分け、混ぜない。

1. **injection 契約** — BOM を `<scope>import</scope>` した最小 downstream consumer を実際に build し、
   effective POM 上で**全 managed 座標**の version が pom.xml の pin と一致することを検証する。
   Maven の model 解決だけで済むので、第三者 artifact を1つも落とさずに全座標を見られる。
2. **resolution + compile 契約** — pin が実在して resolve でき、その jar に対して compile が通ることを検証する。
   registry と認証に依存するため、**public な座標は secret 無しで常時**検証し、
   認証が要る座標は `UNVERIFIED` として**個別に列挙**する（黙って skip しない）。

public / private の宣言は `pom.xml` に置く。既存の `<!-- bom 例外: 理由 -->` と同じ形で
`<!-- bom registry: central -->` / `<!-- bom registry: github -->` を pin の隣に書き、**未宣言は fatal**。

## なぜ（WHY）

**BOM の製品価値は保証そのものであり、保証に証明が無いなら価値も無い。**

- 現行 CI の 2 ゲートは、存在しない pin を**両方素通しする**（実測 `mvn -N validate` exit=0 /
  drift checker exit=0）。壊れるのは release 後の下流。
- しかも `ci.yml` は「dependencyManagement の解決可否を検証する」と**書いてある**。
  読んだ人は検証済みだと信じる。実装の無い保証は、保証が無いことより悪い。
- 検出できていない事故の型が、**この repo が作られた原因そのもの**（CHANGELOG `[2026.48]`）。
  同一座標・中身違いの artifact は version 文字列比較では原理的に検出できず、
  解決済み jar への compile でしか捕まらない。

## 実測（すべて main = 9f581fb の実物に対して取得）

| 観測 | 値 |
|------|-----|
| `building-hierarchy` を架空の `0.19.5` にしたときの `mvn -B -N validate` | **BUILD SUCCESS / exit=0** |
| 同上での `check-bom-version-drift.py` | **exit=0** |
| BOM を隔離 local repo に install → import した consumer の effective dependencyManagement | **12 座標すべてに pin が注入された** |
| version 省略の `<dependency>` 4 件 | **すべて pin が注入された**（3.0.11 / 3.6.0 / 12.1.0 / 0.19.4） |
| Maven Central から secret 無しで取れる managed 座標 | **12 中 5**（残り 7 は 404） |
| `unlaxer-common:3.0.11` の `org.unlaxer.CodePointIndex` | `public static ... of(int)` と `ZERO` が**存在**（javap） |
| 実行環境 | OpenJDK 21.0.2 / Apache Maven 3.9.9 |

## 選択肢と却下理由

| 案 | 却下理由 |
|----|----------|
| **A. 既存 `check-bom-version-drift.py` に相乗り** | 責務が違う。既存は「BOM を真実として consumer の書き方を静的に正す」、今回は「BOM の pin 自身が下流で成立するかを実 build で確かめる」。実行時間も失敗モードも別で、混ぜると `--hook`（PreToolUse）が Maven を起動しかねない。**ただし BOM の読み取りは共有する**（`managed_versions()` を import。README の「判定を緩めた別実装を作らない」方針に従う） |
| **B. CI で全 12 座標を GitHub Packages 認証つきで解決させる** | CI に `read:packages` secret が必須になり、fork PR で常に落ちる。CHANGELOG `[2026.48]` に「secret 未設定の CI でも通ること」を実測で確認した経緯があり、それを捨てることになる |
| **C. registry の public/private を runtime に推測（Central へ問い合わせて 404 なら private 扱い）** | 宣言が要らない代わりに **fail-open** になる。`unlaxer-common` が `3.0.99` に typo されても「private だから未検証」と判定して通してしまう。捕まえたい失敗が捕まらない |
| **D. registry 一覧を ci.yml や別ファイルに持つ** | pom.xml が「現在値の真実」という既存の設計判断に反する二重管理 |
| **E. compile までせず resolve だけ** | 創業事故（同一座標・中身違い）が検出できない。resolve は成功して compile だけが落ちる型だった |
| **F. 何もせず ci.yml のコメントだけ実態に合わせる** | 一番安いが、保証は増えない。存在しない pin は依然 release できる |

**採用は A の否定形 + C の否定形**: 新規スクリプト（BOM 読み取りのみ共有）+ pom への明示宣言（fail-closed）。

## 付帯の判断

- **未宣言 registry を fatal にする。** 新しい座標を BOM に足す人に「これはどこから取れるのか」を必ず答えさせる。
  黙って未検証枠に落ちるのが一番危ない。
- **exit code を 3 値にする。** 0=契約成立 / 1=契約違反 / 2=実行不能（Java・Maven 不在、Central 到達不可）。
  「壊れている」と「確かめられなかった」を混同しない。
- **トークンは CLI 引数で受け取らない。** 環境変数のみ。`ps` にも出力にも残さない。
- **隔離した local repository を毎回使う。** `~/.m2` を汚さず、cache 状態に結果が依存しない（再実行の決定性）。
- **`central` 宣言が 1 件も無い BOM は fatal。** 全部 `github` にすれば検証が空になる、という抜け道を塞ぐ。

## reality-check の結果を受けた追加判断（反復 2-3）

記録と証拠: [../sessions/2026-09-05-bom-consumer-contract-reality-check.md](../sessions/2026-09-05-bom-consumer-contract-reality-check.md)

独立評価者 2 名が実 artifact を操作して critical 2 件・high 3 件を出した。最も重い指摘は
**「未検証の座標が 7 つあるのに、要約と exit code は BOM 全体の成功を主張していた」**。
評価者は github 座標を架空の `99.99.99` にして CI と同じ実行が green になることを実証した。

これに対する判断は「検証範囲を広げる」ではなく **「主張を実態に合わせ、完全検証を release に置く」**。

- PR の CI は secret を持たない設計を維持する（CHANGELOG `[2026.48]` で
  「secret 未設定の CI でも通る」ことを実測で確認した経緯を捨てない）
- 代わりに `--require-all` を追加し、`publish.yml` の deploy 前に
  `--include-github --require-all` を通す。**release だけが完全検証を要求する**（fail-closed）
- 既定の実行は「部分検証」と名乗り、未検証座標では pin が架空でも検出できないことを毎回言う

あわせて `<java.baseline>` を宣言必須にし、解決した jar の class file version を実測する。
compile は通って実行時だけ `UnsupportedClassVersionError` になる型は compile 検証では
捕まらないため、bytecode を直接読む。

**`publish.yml` を変えることの意味**: release トークンに `read:packages` が無い場合、
publish はここで止まる。これは意図した fail-closed であり、
「確かめられないまま publish する」より安全だと判断した。止まったときの対処は
エラーメッセージが名指しする。

## 互換性

- `scripts/check-bom-version-drift.py` は**一切変更しない**。3 入口（CLI / `--staged` / `--hook`）の挙動も不変。
- `pom.xml` への追加は**コメントのみ**。座標・version・property は変わらないため、
  BOM を import している既存 consumer への影響はゼロ（effective POM が同一）。
- 追加コメント `bom registry:` は既存の例外パターン `bom\s*例外\s*:` に一致しないため、
  drift checker の `has_reasoned_exception()` を誤って発火させない（テストで固定する）。
- CI は step を 1 つ増やすのみ。secret は追加しない。

## 巻き戻し

この PR の revert だけで完全に戻る。永続する副作用は無い。

```bash
git revert -m 1 <merge commit>
```

戻した後に green を確認する範囲:

```bash
mvn -B -N validate
python3 -m unittest discover -s tests -v
python3 scripts/check-bom-version-drift.py --bom pom.xml pom.xml
```

pom.xml の変更はコメントのみなので、部分的に戻したい場合は
`scripts/verify-bom-consumer-contract.py` の呼び出しを ci.yml から外すだけでも CI は green に戻る
（`bom registry:` コメントは無害に残る）。

## tramli / tramli-appspec の適合性評価

**不採用。** 5 軸すべて ×:
human-in-the-loop（同期実行、承認なし）/ 長期状態（隔離 local repo で完結、実行間に state を持たない）/
補償（副作用は temp のみ、削除で済む）/ 外部 event（契機は CI・手動のみ）/
requires-produces 契約（install → effective-pom → compile の直列 3 段、関数合成で足りる）。

tramli README 自身が「外部 event が無いなら Pipeline すら推奨しない」「2〜4 段の直列は関数合成」と述べており、
導入は「抽象化のためだけの導入」になり minimal primitives / YAGNI に反する。

`tramli-appspec` の skill は `applies_when: repo.has_file: pom.xml` でこの repo にマッチしてしまうが、
これはファイル名レベルの一致であり構造的適合ではない（unlaxer-bom は `src/` を持たない pom-only repo）。

**再検討条件**: BOM 検証が「複数 registry へ publish → 外部の下流 repo で検証 → 結果を待って promote」という
**外部 event を待つ長時間フロー**になったとき。epic #1 Phase 3（`vacant-bom` 新設・両 remote へ publish）が
その形に近づく可能性があり、そこで再評価する。
