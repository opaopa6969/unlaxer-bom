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

## 反復 4 — 独立評価者 2 名で再評価（対象 commit `4822aad`）

前回の指摘も修正内容も一切知らない**新規 context** の評価者 2 名。persona は反復 3 と同型
（初見の新規採用者 / 既存 version 互換を疑う保守者）。別 tmp dir・別 Maven local repository。

### 完了観測

| 観測項目 | 評価者 c（採用者） | 評価者 d（保守者） |
|----------|--------------------|--------------------|
| critical | **0** | **0** |
| 追加説明なしで主要 task 完了 | **Yes**（README → `mvn install` → 自作 consumer → `mvn compile` の 3 手、詰まりゼロ） | **Yes** |
| 自分の状態・版を自分の言葉で説明 | **Yes**（未検証 7 座標を「壊れている」でなく「確かめられなかった」と区別） | **Yes**（保証すること / しないことを列挙） |
| `~/.m2` 無変更 | 確認済み | 確認済み（前後とも 0 件） |
| 再実行の決定性 | 出力完全一致 | 出力完全一致（offline cache 済みでも同一） |
| secret 非露出 | 検出ゼロ | working tree・**全 git 履歴**を grep して検出ゼロ |

### 反復 3 の修正が効いたことの確認（評価者 d の破壊実験 11 種）

**11 種すべてが exit 1 / 2 で失敗し、すべて座標名と対処法を含んだ。**
評価者 d の総括: 「座標を名指ししない・黙って skip する・exit 0 なのに一部しか調べていない、
という失敗パターンは **1 件も見つからなかった**」。

内訳: 架空 version / 中身違いの版（創業事故の再現）/ `bom registry` 未宣言 / `<version>` 削除 /
未定義 property / 同一座標の重複 pin / `java.baseline` 削除・非数値・低すぎる値 / `bom registry` の typo。

### 反復 4 の high 3 件と、その処理

| # | 指摘 | 処理 |
|---|------|------|
| d-1 | 実在するが「意図と違う」版（`flyway 12.1.0` → 実在する `11.8.2`）は検出しない | **停止**（下記） |
| d-2 | consumer の明示 version 上書き・低すぎる `--release` を Maven は検出しない。防御は opt-in | **スコープ外**。consumer repo 側での導入・運用の問題であり、この repo 単独では強制できない。README に「BOM は明示 version に負ける」ことを明記した |
| d-3 | github 7 座標は無資格 CI では証明されず、第三者は再現できない | **可能な範囲で対応済み**。private registry である以上、残余は消せない。README に第三者が取れる 2 つの選択肢（自分で `--require-all` を回す / publish ワークフローの green を受け入れる）を明記し、採用側が明示的に決める形にした |
| c-1 | GitHub Packages 座標が認証なしで `in central` としか出ず詰む | **修正**。README に consumer 側の `<repositories>` + `settings.xml` 設定手順（`<id>` 一致の必要性、実値を書かない書き方）を追加 |
| c-2 | 「消せなかった場合は場所を出す」約束が 1 回破られた（非再現） | **修正**。強制終了されると `finally` 自体が走らないため、作業用ディレクトリを**生成した時点で** stderr に出す形にした。約束が kill されても成立する |
| c-3 | README の Java 記述が不正確（直接 compile ならその場で落ちる） | **修正**。実測どおり 2 ケース（直接 compile / 別環境で実行）に分けて記述 |
| d-4 (medium) | `java.baseline` は consumer に伝播しない | README に明記（import scope は dependencyManagement しか運ばないため機構上必然） |
| d-5 (low) | 2 スクリプトで未解決 property の exit code の意味が違う（2 と 1） | README に明記。drift checker の 2 は PreToolUse hook で編集を止める値なので意図的に変えない |

## 停止理由 — d-1「実在する別版への打ち間違い」

**同一原因で 2 回報告され、2 回目も検出改善に至らなかったため、この gap の反復をここで止める。**

- 反復 3（評価者 b）: `doma 3.6.0` → 実在する `3.5.0` で全部通る
- 反復 4（評価者 d）: `flyway 12.1.0` → 実在する `11.8.2` で全部通る

反復 3 での対応は**開示のみ**（「意図した版であることは保証しない」を出力と README に常時明記）で、
検出は増えていない。反復 4 でも同じ結論に達した。

**検出には別の真実源が要る。** この repo は「意図した版」を README 表 / CHANGELOG / history にも
持っており、突き合わせれば片方だけの打ち間違いは捕まえられる。しかしそれは
**「BOM を真実として docs を正す」という別の原語**であり、本 slice（「pin は実際に解決でき、使える」）に
混ぜると PR が 2 つの原語を持つ。GAP-04 として最初から保留していた領域でもある。

→ **issue #10 として切り出した。** 本 PR では扱わない。
評価者 d の評価も「隠された嘘ではない」であり、条件付き Yes の結論を妨げていない。

## 完了判定

| 完了条件 | 結果 |
|----------|------|
| critical = 0 | **満たす**（反復 4 の評価者 2 名とも 0） |
| high 修正 | 修正 3 件 / スコープ外 1 件 / 残余開示 1 件 / 停止 1 件（issue #10 へ切り出し）。**すべて未処理のまま残していない** |
| 全評価者が追加説明なしで主要 task 完了 | **満たす**（反復 4 の 2 名とも Yes） |
| 全評価者が自分の状態を説明できる | **満たす** |
| 回帰 green | **満たす**（`mvn -N validate` / 56 テスト / drift checker の 3 入口 / consumer 契約 E2E） |
| 反復数 | 5（上限 5 以内） |

> 再掲: **これは合成ユーザーによる事前評価であり、現実の利用者に効くこと、購買意欲、継続利用、
> 業務成果を証明しない。**
