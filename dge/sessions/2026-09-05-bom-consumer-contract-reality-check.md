# reality-check-loop 記録 — BOM consumer 契約（GAP-01 / issue #9）

- 由来: [2026-09-05-bom-consumer-contract.md](./2026-09-05-bom-consumer-contract.md)
- 設計判断: [../decisions/2026-09-05-bom-consumer-contract.md](../decisions/2026-09-05-bom-consumer-contract.md)
- 実装仕様: [../specs/2026-09-05-bom-consumer-contract.md](../specs/2026-09-05-bom-consumer-contract.md)

> **これは合成ユーザーによる事前評価であり、現実の利用者に効くこと、購買意欲、継続利用、
> 業務成果を証明しない。** 実在の採用者が同じ判断をする保証はない。

## 評価契約（実装前に固定した）

| 項目 | 固定値 |
|------|--------|
| persona | (a) 初見の新規採用者 (b) 既存 version 互換を疑う保守者 |
| 状況 | 同僚から「これでバージョンを揃えろ」と渡された / 次の release で採用可否を決める |
| 主要 task | (a) BOM から版を得る consumer を実際に build し、自分が乗っている版を正確に言える (b) 「stated version set は信頼できるか、間違っていたら何かが教えてくれるか」に実 build で決着 |
| 最初の価値 | README から出発して最初に何かが本当に動くまで |
| 完了観測 | 追加説明なしで主要 task 完了 + 自分の状態を自分の言葉で説明できる |
| 誤認・不可逆・安全失敗 | 過大主張（確かめていないのに成立と言う）/ 黙って検査対象から消える / secret 露出 / registry への書き込み |
| 対象環境 | OpenJDK 21.0.2 / Maven 3.9.9 / Linux。評価者ごとに別 tmp dir・別 Maven local repository |
| 主要経路 | BOM を隔離 local repo に install → import scope の consumer を実 build |
| 既存回帰 | `mvn -N validate` / 既存 unittest / `check-bom-version-drift.py` の 3 入口 |
| 権限 | read/実行のみ。`mvn deploy`・`git push`・`~/.m2` 書き込み・registry publish は禁止 |
| 一次証拠 | online/offline・dependencyManagement/import scope・未指定/未知 property・Java/Maven 対応範囲・エラー診断・再実行の決定性・secret 非露出 |
| 未採点条件 | artifact / build / commit が識別できない報告は採点しない |
| 完了条件 | critical=0、high 修正、全評価者が追加説明なしで主要 task 完了・状態説明、回帰 green |
| 上限 | 最大 5 反復。同一原因で 2 回改善なしなら停止理由を記録 |
| 評価者 | 会話履歴・既知 gap・意図解・他者の採点を渡さない新規 context。答えは渡さない |

## 反復 1 — 実装（commit `f652ce3`）

**利用者証言（想定）**: 「import したら本当にその版が入って、動くのか」だけが知りたい。

**専門家反論（主担当の実測）**: 現行 CI はそれを見ていない。
`pom.xml` の `building-hierarchy` を架空の `0.19.5` にすると
`mvn -B -N validate` は BUILD SUCCESS、`check-bom-version-drift.py` は exit 0。**両ゲート素通し。**

**設計判断**: 原語を 1 つ追加（「pin は実際に解決でき、使える」）。injection と
resolution + compile の 2 軸に分け、registry 宣言で対象を分ける。

**Gap**: 実測で Central 上の `unlaxer-common:2.8.0` を pin すると、既存 2 ゲートが exit 0 のまま
新検証だけが `cannot find symbol: method of(int) / variable ZERO` で落ちる
＝ 創業事故（CHANGELOG `[2026.48]`）が現物で再現・検出された。

## 反復 2 — 主担当の自己検証（commit `a7999bb`）

**利用者証言（自己）**: BOM 自身が壊れているのに「確かめられなかった」と言われると、
CI ログを読む人は環境の問題だと誤読する。

**専門家反論**: `PomError`（POM を読めない / pin の property を解決できない）を exit 2 に
落としていた。これは環境ではなく BOM の欠陥。また `--keep` すると
`settings.xml` にトークンの実値がディスクに残っていた。

**設計判断**: `PomError` → exit 1。exit 2 は環境の問題だけに限定。
認証情報は Maven の `${env.*}` 補間に任せ、値をプロセスにもディスクにも持たない。

**Gap（実測）**: `GH_PKG_TOKEN=SUPER-SECRET-TOKEN-VALUE` を渡して `--keep` しても、
生成物のどこにも実値が現れないことを確認。GitHub Packages の 401 は exit 2 に分類されることも確認。

## 反復 3 — 独立評価者 2 名（対象 commit `f652ce3` → 修正 commit `4822aad`）

評価者は別 tmp dir・別 Maven local repository で、それぞれ**自作の** downstream consumer を
実 build した（この repo の生成スクリプトに依存しない検証を含む）。

### 利用者証言（評価者 a: 初見の新規採用者）

- README の「使い方」例（`building-hierarchy`）を**そのまま貼っても動かない**。
  `Could not find artifact ... in central` としか出ず、理由がどこにも書いていない。
  `pom.xml` の `bom registry: github` コメントに自力で気づいて初めて分かった → **high**
- `unlaxer-common:3.0.11` の class file version は 65（Java 21）。JDK 17 を用意して実測すると
  **compile は通り、実行時に `UnsupportedClassVersionError`** で落ちた。Java 要件はどこにも無い → **high**
- 一時ディレクトリの自己削除が 3 回中 1 回失敗し、`ignore_errors=True` のため無警告で残った → medium
- offline 挙動が無文書。`<server id>` 一致で無関係な資格情報が送られる経路の注意も無い → medium
- 良かった点: injection は全 12 座標で pin どおり。決定性・`~/.m2` 非汚染は本当に守られていた。
  「壊れている」と「未検証」を分ける姿勢は誠実

### 専門家反論（評価者 b: 既存 version 互換を疑う保守者）

- **critical**: github 座標を架空の `99.99.99` にして、**CI と同じ実行（secret 無し）が exit 0 で
  「契約成立」**になることを実証。行ごとには `UNVERIFIED` と書くのに、要約と exit code は
  BOM 全体の成功を主張していた。「急いだ release 担当が打ち間違えても green」
- **critical**: managed dependency から `<version>` を落とすと、表が 12 行から 11 行に減るだけで
  exit 0。**両スクリプトのどちらも「1 件消えた」と言わなかった**
- **high**: `doma 3.6.0` → 実在する `3.5.0` に変えても全部通る。この道具は自己整合性を証明するだけで
  「意図した版か」は見ていない
- **high**: Java 下限が宣言も強制もされていない（評価者 a と独立に同じ結論）
- medium: 無効トークンが「ネットワーク障害」に分類され、トークンを疑えない
- medium: `MAVEN_OPTS` の proxy 指定は Maven の resolver に効かず、offline を試したつもりで
  通信していた（監査者が自分を騙しうる）
- 守れていた点: injection 12/12 を**自作 consumer と自作の effective-pom 解析で独立に確認**。
  決定性は jar の SHA-256 まで一致。secret 露出なし。`~/.m2` 無変更。
  創業事故の再現も live data で成立

### 設計判断（反復 3 の応答）

| 指摘 | 判断 |
|------|------|
| 未検証があるのに「契約成立」 | 要約を「**部分検証**」に変更。未検証座標では pin が架空でも検出できない旨を毎回出力。`--require-all` を追加し、未検証が残れば exit 1。**`publish.yml` の deploy 前**に `--include-github --require-all` を通し、release だけが完全検証を要求する（PR の CI は secret 無しのまま） |
| `<version>` 欠落が黙って消える | version の無い managed dependency を fatal にし、座標を名指しする |
| Java 下限が無い | `pom.xml` に `<java.baseline>21</java.baseline>` を宣言（未宣言は fatal）。解決した jar の class file version を実測して下限超過を契約違反にする。compile では捕まらない型なので bytecode を直接読む。multi-release jar の `META-INF/versions/` は除外 |
| 「正しい版か」まで保証すると読める | 保証しないことを出力と README に常時明記。**意図した版との突き合わせは GAP-04（docs↔pom 整合）の担当**として繰り上げ記録 |
| 無効トークンの誤診 | 401/403 を認証の問題として切り分け、`read:packages` の確認を促す |
| 後始末の失敗が無警告 | 削除できなければ場所を stderr に出す |
| README の穴 | 使い方の直後に「これだけでは resolve できない座標がある」、動作要件（Java 21 / Maven 3.9）、offline の試し方、`server id` 一致の注意を追記 |

### Gap（反復 3 の実測・修正後）

| 再現ケース | 修正前 | 修正後 |
|------------|--------|--------|
| github 座標を架空の `99.99.99` に | exit 0「契約成立」 | 既定は exit 0 だが「部分検証」+ 未検証座標では検出できない旨を明示。`--require-all` は exit 1。release は通らない |
| managed dependency の `<version>` 削除 | exit 0・表が黙って 11 行 | **exit 1**「version の無い dependency があります: org.unlaxer:historical-town-names」 |
| `java.baseline` を 17 に下げる | 検査自体が無かった | **exit 1**「unlaxer-common:3.0.11: Java 21 が必要（BOM 宣言の下限は Java 17）」 |
| `java.baseline` 未宣言 | 同上 | **exit 1** |
| 無効トークンで `--include-github` | exit 2「ネットワークまたは環境の問題」 | exit 2「**認証**の問題。401/403。read:packages スコープを確認」 |

**繰り上げ記録 — GAP-04（docs↔pom 整合）**: 評価者 b が独立に到達した
「実在する別版への打ち間違いは検出できない」は、CHANGELOG / README / history と pom を
突き合わせる GAP-04 の担当領域。本 PR では扱わないが、優先度を上げて記録する
（issue #6 の 4 トレイン分の drift 実績に、この証言が加わった）。

**スコープ外と判断**: 「plain Maven は consumer 側の version 上書きを検知しない」（評価者 a）。
これは既存 `check-bom-version-drift.py` の担当であり、consumer repo 側での導入・運用の問題。
本 slice では扱わない。
