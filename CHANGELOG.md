# unlaxer-bom リリーストレイン履歴

各トレイン（CalVer `YYYY.MM`）の検証済みバージョンセットと、その**検証エビデンス**を記録する。
現在値の真実は `pom.xml`、本ファイルは過去全トレインと根拠を持つ（二層管理）。
新トレインは上に積む。

## [2026.35] - 2026-08-03

> 変更: onigiri-parser 0.9.17 → **0.9.18**（登記字名辞書 registry-aza-names #99 —
> 登記所備付地図由来 35.6万タプル・市区町村スコープ・フラグ opt-in）。
>
> **追加挙動**: -Donigiri.parser.registryAzaDict=true 時、町名マッチ後の残りを登記字名と
> 最長一致で町名後小字(L450)へ消費。岩手の地割（第８地割 = chome 型 1,068 行）と
> 大字+字名連結（滝沢市鵜飼字狐洞 → 鵜飼狐洞）が解決する（adoyose#36）。既定 off なので
> フラグ未指定の利用側は挙動不変。
>
> **検証エビデンス**: adoyose engine（フラグ有効・bom 2026.35）で spec 90 green +
> 正規化ペアベンチ 2,981 件 正例 100.00% / 誤マージ 0.00% を維持（地割ケース追加込み）。

## [2026.34] - 2026-08-03

> 変更: building-hierarchy 0.19.0 → **0.19.1**（stripHonorific の建物語彙ゲート —
> 「<宛名>様方」の宛名を建物名として返さない。adoyose#32）、
> abr-utils 0.10.11 → **0.10.12**（EmbeddedPostcode: 〒前置郵便番号の分離 #48 /
> (丁目)/(番地) 分割町域の裸ハイフン3連鎖で丁目側 zip を primary に adoyose#34 /
> ChomeTownExporter: ABR 丁目持ち町字リスト 22,684 町字の生成）。
>
> **追加挙動**: postcode-resolve が 〒NNN-NNNN 前置入力を受理し embeddedZip /
> embeddedZipAgrees を表出。building-hierarchy 経由の建物名ヒントが宛名（田中様方）を
> 返さなくなり、onigiri パイプラインで方書きが 1400 に正しく載る。
>
> **検証エビデンス**: abr-utils 150 テスト green + 1M 計測（候補 99.96% / primary 99.80%、
> v14 と失敗集合 diff ゼロ）。building-hierarchy 313 テスト green。
> adoyose engine（bom 2026.34 + 同梱 abr-chome-towns.tsv）89 spec green、
> 正規化ペアベンチ 2,981 件で正例一致 100.00% / 誤マージ 0.00%
> （ABRUtils docs/llm-parser-bench-20260801.md）。

## [2026.33] - 2026-07-26

> 変更: onigiri-parser 0.9.16 → **0.9.17**（建物名パターンの DebugStatus タグ化）、
> building-hierarchy 0.18.0 → **0.19.0**（BuildingPatternScorer / ForwardTailParser /
> DuelArbiter — 両方向スキャナと調停）。
>
> **追加挙動**: with-bh 構成では建物名の判定根拠（接頭語+固有名詞+接尾語 のパターン種別）が
> DebugStatus の boolean タグ（建物名パターンXXX）として記録される。enum は末尾追加で
> 既存 ordinal 不変（ResolverResultKindOfBooleanOrdinalPinTest で固定）。
> BH の DuelArbiter.arbitrateDetailed は tail/forward 両方向の分解と選択規則を返す
> （エンジンの building.scanners JSON の素材）。
>
> **検証エビデンス**: onigiri 336 run / 既存 baseline 6 failures のみ（変更前後で同一）。
> BH gold 95 件: duel-arbiter 建物名 96.6%・部屋 100%。BH 実住所 20 万行の
> 両方向比較は building-hierarchy docs/scanner-duel-experiment.md。

## [2026.32] - 2026-07-26

> 変更: onigiri-parser 0.9.15 → **0.9.16**（`ZipAddress#町名省略可`）。
> 他 artifact は 2026.31 から変更なし。
>
> **挙動変更**: 掲載外代表番号（「以下に掲載がない場合」= 町名が空の zip）と
> 「〜一円」（自治体全域表記）の zip で、入力に町名が現れなくてもエラーにせず
> 先へ進むようになった（`郵便番号情報町名取得失敗エラー` / `町名分割エラー` の減少）。
> 「塩尻市岩垂」（399-0700）や「東京都利島村87」（100-0301 利島村一円）が
> 町名分割エラーにならず valid になる。
> interface には default メソッド追加のみで **binary 互換**（実装側の変更不要）。
>
> **検証エビデンス**: onigiri テスト 336 run / 既存 baseline failure 6 のみ
> （変更前後で同一・新規 failure なし）。adoyose E2E 26 ケースで 18/26 → 22/26
> （エラーが正解の 1 件を除き改善はこの 4 件）。adoyose prod で稼働確認済み。

## [2026.30] - 2026-07-20

> 変更: building-hierarchy 0.16.0 → **0.17.0**（様方バグ修正 #40 / TailSignals の実算出 /
> publish ワークフロー追加）。他 artifact は 2026.29 から変更なし。
>
> **バグ修正**: `様方` の直前の氏名が残り部屋番号抽出が失敗していた。
> `恵比寿ビル402号室 山田様方` が建物名 `恵比寿ビル402号室 山田` になっていた。
> 実データの「様方」はほぼ確実に氏名を伴うため、実質「様方」付き住所が全滅していた。
> **建物名の名寄せキーが変わる**ので、既存の名寄せ結果を持つ側は再計算が要る。
>
> 追加: `TailSignals`（分解結果から観測事実を立て候補列を返す）。
> サフィックス明示時は候補 1 つ、分解できなくても建物名が数字で終われば候補を返す（`森ビル13`）。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.3.2 |
| building-hierarchy | `org.unlaxer` | **0.17.0** |
| abr-utils | `org.unlaxer.geo` | 0.10.11 |
| onigiri-parser | `org.unlaxer` | 0.9.15 |
| historical-town-names | `org.unlaxer` | 0.1.0 |
| municipality-history | `org.unlaxer` | 1.0.1 |

検証: building-hierarchy 305 件全パス。

## [2026.29] - 2026-07-20

> 変更: building-hierarchy 0.15.0 → **0.16.0**（裸の漢数字を部屋番号に分解 / onigiri-parser#96）。
> 他 artifact は 2026.28 から変更なし。
>
> `…ビル四百二` が部屋番号に分解されず建物名に残っていた。`四百二号`（号付き）や `402`（算用数字）は
> 分解できるのに裸の漢数字だけが落ちる非対称があった。
>
> **後方互換に注意**: 分解の確信度が変わる。`RoomNumberBasis`（判定根拠）を導入し、
> `…ビル402` の確信度が 1.00 → **0.80** に下がる。号室サフィックスが無い以上これも推測であり、
> 従来満点で返していたのが不正確だったため（精度を上げたのではなく正直になった変更）。
> 確信度を消費している側は閾値の見直しが要る。`BuildingTailParser.parse()` の
> シグネチャは互換維持で、根拠が要る呼び出し側は `parseDetailed()` を使う。
>
> 裸漢数字の誤検出ガードとして「千」「万」を含む run を不採用にしている
> （`ハイツ八千代`=8000・`コーポ千代田`=1000 が部屋番号として妥当な範囲に見え、地名・人名に頻出するため）。
> あわせて `TailInterpretation` / `TailSignal` / `TailCandidate`（末尾裸数字の複数候補＋スコア根拠）を追加。
> `森ビル13` のように数字まで含めて建物名のケースがあり、文字列だけでは解釈が決まらないため。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.3.2 |
| building-hierarchy | `org.unlaxer` | **0.16.0** |
| abr-utils | `org.unlaxer.geo` | 0.10.11 |
| onigiri-parser | `org.unlaxer` | 0.9.15 |
| historical-town-names | `org.unlaxer` | 0.1.0 |
| municipality-history | `org.unlaxer` | 1.0.1 |

検証: building-hierarchy 283 件全パス。adoyose engine 71 件全パス（0.15.0 参照時）。

## [2026.28] - 2026-07-08

> 変更: japanese-parser-common 0.1.1 → **0.3.2**(CharType enum 追加 = 文字種の排他9分類を型に昇格、
> kindsOf range種別修正、kugiri由来 aza パッケージ等 0.2〜0.3系の取り込み。設計原則「enum化できるものは
> enum化する(type safe)」)。追随して onigiri-parser 0.9.14 → **0.9.15**、abr-utils 0.10.10 → **0.10.11**
> (いずれも jpc 0.3.2 でコンパイル・テスト検証済み。onigiri の既存失敗6件は 0.1.1 でも同一に失敗する
> 環境依存でありトレイン起因の退行なし)。素性キー等の文字列表現は CharType.name() で不変。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | **0.3.2** |
| building-hierarchy | `org.unlaxer` | 0.15.0 |
| abr-utils | `org.unlaxer.geo` | **0.10.11** |
| onigiri-parser | `org.unlaxer` | **0.9.15** |
| historical-town-names | `org.unlaxer` | 0.1.0 |
| municipality-history | `org.unlaxer` | 1.0.1 |

検証: jpc 94 / kugiri 38 / abr-utils 76 全パス、onigiri 333中327パス(既存環境依存6のみ)。

## [2026.27] - 2026-06-25

> 変更: abr-utils 0.10.9 → **0.10.10**（area-key sidecar で lg_code を、dates sidecar で efct/ablt を
> snapshot から引けるように / ABRUtils#18・#38。develop の structured resolver / 存在索引 compact-v2 は維持）。
> 他 artifact は 2026.26 から変更なし。abr-historical(sibling)は未publishのため BOM 未登録。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.1.1 |
| building-hierarchy | `org.unlaxer` | 0.15.0 |
| abr-utils | `org.unlaxer.geo` | **0.10.10** |
| onigiri-parser | `org.unlaxer` | 0.9.14 |
| historical-town-names | `org.unlaxer` | 0.1.0 |
| municipality-history | `org.unlaxer` | 1.0.1 |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.26] - 2026-06-25

> 変更: building-hierarchy 0.14.1 → **0.15.0**（教師あり同定 `learned` 戦略を追加 / building-hierarchy#38）。
> 既定の同定戦略は `normalized` のまま。`learned` は包含・対立度・3値化・部屋証拠の特徴量で
> 建物名の表記ゆれ併合(recall)と共通種別語の衝突分離を改善（ペア F1 0.750→0.917 / site 建物数 MAE 0.200→0.000）。
> building-hierarchy 249 テスト緑。他 artifact は変更なし。リリース連鎖: building-hierarchy#39。
> (注) CHANGELOG は 2026.22〜2026.25 のエントリが未記載。各バージョンの真実は `pom.xml` を参照。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.1.1 |
| building-hierarchy | `org.unlaxer` | **0.15.0** |
| abr-utils | `org.unlaxer.geo` | 0.10.9 |
| onigiri-parser | `org.unlaxer` | 0.9.14 |
| historical-town-names | `org.unlaxer` | 0.1.0 |
| municipality-history | `org.unlaxer` | 1.0.1 |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.21] - 2026-06-16

> 変更: onigiri-parser 0.9.9 → **0.9.11** / japanese-parser-common 0.1.0 → **0.1.1**、
> **historical-town-names 0.1.0 / municipality-history 1.0.1 を新規追加**。
> (1) 0.9.10: hierarchyOracle を町域範囲判定(TownRangeCheck)にリネーム(旧プロパティキー後方互換)、
> BlockSpaceNormalizer を CharacterKind ベースに書き直し(正規表現排除)。
> (2) 0.9.11: 町名照合に失敗した字を歴史地名辞書(historical-town-names)で町域として消費する
> 最終 fallback を追加(ABR/JP/字プレフィックス全失敗時のみ・住所向け最長一致・建物 suffix 除外)。
> jpc 0.1.1: delimitorSpace に各種空白(タブ/ノーブレーク/Unicode スペース)を追加。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | **0.1.1** |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.8 |
| onigiri-parser | `org.unlaxer` | **0.9.11** |
| historical-town-names | `org.unlaxer` | **0.1.0**(新規) |
| municipality-history | `org.unlaxer` | **1.0.1**(新規) |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.20] - 2026-06-16

> 変更: onigiri-parser 0.9.8 → **0.9.9**(他据置)。番地ブロック内の空白を詰める
> `BlockSpaceNormalizer` を parse 入口(parseOverAll)に追加。「○○1丁目 53-15」のように
> 丁目と番地の間に半角/全角スペースが入ると、スペースが文字種境界で block を分断し
> 番地-号が建物階層へ誤配置されていた不具合を解消(後ろが数字の空白のみ詰め、建物名前の
> 空白は残す)。base / AbrFallback(indexer)両 parser で有効。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.1.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.8 |
| onigiri-parser | `org.unlaxer` | **0.9.9** |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.19] - 2026-06-16

> 変更: abr-utils 0.10.7 → **0.10.8**(他据置)。0.10.7 の存在辞書 地番 union を **revert**。
> union は件数・救済 churn に無効果な一方、飛び番の地番を go-set に混ぜて辞書を肥大化させ
> 起動 build と parse を遅くしていた(地番多発エリアで約2倍)。RESIDENTIAL 優先の元挙動に戻す。
> 地番の枝番誤降格対策は「地番住所では範囲判定を効かせない」方向で別途。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.1.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | **0.10.8** |
| onigiri-parser | `org.unlaxer` | 0.9.8 |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.18] - 2026-06-16

> 変更: abr-utils 0.10.6 → **0.10.7**(onigiri 0.9.8 / jpc 0.1.0 据置)。存在辞書の地番取りこぼし regression 修正。
> `findChomesNode` が RESIDENTIAL/LOT_NUMBER の先勝ちで、両体系を持つ行で地番(LOT_NUMBER)を捨てていた。
> 両 notation を **union** で index するよう修正(hasChome/hasGoLayer/hasGo がどちらかにあれば true)。
> → 町域範囲判定が地番を部屋番号へ誤降格する不具合を解消(照合品質向上)。dual-notation パリティテスト追加。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.1.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | **0.10.7** |
| onigiri-parser | `org.unlaxer` | 0.9.8 |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.17] - 2026-06-16

> 変更: onigiri-parser 0.9.7 → **0.9.8**(abr-utils 0.10.6 / japanese-parser-common 0.1.0 据置)。
> `AbrFallbackStats.wasLastParseRescued()` を追加 — ABR 救済が実際に doc 化へ寄与した parse を per-thread で
> 観測可能に(上位 indexing が per-file `abr_fallback_count` に集計するため)。観測のみ・既存挙動不変。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| japanese-parser-common | `org.unlaxer` | 0.1.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.6 |
| onigiri-parser | `org.unlaxer` | **0.9.8** |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.16] - 2026-06-16

> 変更: **japanese-parser-common 0.1.0 を新規追加** + onigiri-parser 0.9.6 → **0.9.7** + abr-utils 0.10.4 → **0.10.6**。
> - **japanese-parser-common**: onigiri から日本語住所テキスト処理(文字種/CodePoint モデル・正規化・tokenizer・
>   translator 核・MatchKind enum・カスタム Lucene CharFilter)を抽出した共通モジュール。onigiri / abr-utils が共有。
>   MatchKind は純 enum 化(ResolverResultValue/Codec は onigiri 残置、sentinel NPE 修正挙動は維持)。
> - **abr-utils 0.10.6**: 構造化住所 resolver(行政剥がし + 町名最長一致、jageocoder/DAMS 流、decode/全件スキャンなし)
>   + 列挙/match public API(prefectures/municipalities/oazaList/matchPrefecture/matchMunicipality)。0.10.5 で生辞書
>   アクセサ公開 + free-text を @Deprecated 化。
> - **onigiri 0.9.7**: 抽出追従 + ABR 救済(AbrZipResolver)を free-text fuzzy → 構造化 resolveComponents へ rewire
>   (free-text は最終手段 fallback)。
> 検証エビデンス: japanese-parser-common 単体 79 tests / onigiri 380 tests / abr-utils 67 tests(構造化 vs free-text
>   比較含む)全 green。各 artifact publish 成功。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| **japanese-parser-common** | `org.unlaxer` | **0.1.0** |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | **0.10.6** |
| onigiri-parser | `org.unlaxer` | **0.9.7** |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.15] - 2026-06-16

> 変更: abr-utils 0.10.3 → **0.10.4**(onigiri-parser 0.9.6 据置)。indexing free-text 救済の高速化。
> `findCompactTreeCandidatesByFreeText` の「n-gram 空振り時の全件線形スキャン(~620K)」を既定 OFF に
> (`-Dabr.freeText.fullScanFallback=true` で従来挙動)。batch indexing で JP 失敗行ごとに踏んでいた
> O(620K) を除去し、n-gram で引ける救済(=doc)は維持。**メソッド署名不変のため onigiri 再ビルド不要**。
> 検証エビデンス: abr-utils CI deploy 成功 / ローカル test green。他据え置き。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | **0.10.4** |
| onigiri-parser | `org.unlaxer` | 0.9.6 |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.14] - 2026-06-15

> 変更: onigiri-parser 0.9.4 → **0.9.6** + abr-utils 0.10.2 → **0.10.3**。indexing 高速化トレイン。
> - 0.9.5: `郵便番号辞書match区` の null MatchKind encode NPE 修正。
> - 0.9.6: ABR hierarchy oracle を**存在辞書(zero-decode mmap, abr-utils 0.10.3 `RegulatedExistenceIndex`)**へ
>   張り替え(lookup 毎の compact-tree decode + cache を撤去)。`AbrFallbackAddressParser` に free-text fallback
>   抑止フラグを追加(indexing worker で全件線形スキャンを回避)。Kuromoji `Pronunciation` を ThreadLocal 化
>   (ファイル内並列化の前提)。
> 検証エビデンス: onigiri-parser CI(test+build)green(380 tests)/ 両 artifact publish 成功。他据え置き。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | **0.10.3** |
| onigiri-parser | `org.unlaxer` | **0.9.6** |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.13] - 2026-06-15

> 変更: onigiri-parser 0.9.3 → **0.9.4** + abr-utils 0.10.1 → **0.10.2**。ABR 有効時の indexing
> スループット低下(synchronized LruJsonCache のロック競合 + 二重 Jackson 変換)を解消する option C。
> abr-utils 0.10.2 に `decodeToJsonNode` / ロックフリー `compactTreeJsonNode(rowId)` を追加し、
> onigiri 0.9.4 が JsonNode を直接消費(String 再パース廃止)+ ロックフリー bounded cache を併用。
> 検証エビデンス: onigiri-parser CI(test+build)green / 両 artifact publish 成功。他据え置き。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | **0.10.2** |
| onigiri-parser | `org.unlaxer` | **0.9.4** |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |

## [2026.12] - 2026-06-15

> 変更: onigiri-parser 0.9.2 → **0.9.3**。ABR regulated-index を mmap on-demand decode 化し
> ABR 有効時の Java heap OOM を解消(heap 数百MB→~10MB級、ABRUtils の mmap 設計を維持)。
> あわせて with-abr/with-bh profile を廃止し abr/bh を default 同梱化(consumer 影響なし)。他据え置き。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.1 |
| onigiri-parser | `org.unlaxer` | **0.9.3** |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |


## [2026.11] - 2026-06-15

> 変更: onigiri-parser 0.9.1 → **0.9.2**（B2 DebugStatus 分岐マーカー追加 + マーカー改名:
> 階層オラクル→ABR範囲判定 / Unlaxer→建物階層リゾルバ）。他据え置き。
> consumer 注意: 旧マーカー名（階層オラクル…）を参照しているコードは新名（ABR範囲判定…）へ追従が必要。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.1 |
| onigiri-parser | `org.unlaxer` | **0.9.2** |
| doma-core / doma-processor | `org.seasar.doma` | 3.6.0 |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | 12.1.0 |


## [2026.10] - 2026-06-15

> 変更: unlaxer-bom を **vacant 製品の共通 BOM** として再定義（2層 BOM 化への布石）。検証済み 3rdパーティとして
> **doma 3.6.0 / flyway 12.1.0** を dependencyManagement に追加（各 rdb 実装・consumer が BOM 経由で版を揃え drift を防ぐ）。
> `jaddress-rdb-api`（rdb port）の枠を予約（公開は Phase 1）。unlaxer artifact 版は据え置き。
> 設計: docs/design/vacant-bom-rdb-architecture.md / tracking: opaopa6969/unlaxer-bom#1。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.1 |
| onigiri-parser | `org.unlaxer` | 0.9.1 |
| doma-core / doma-processor | `org.seasar.doma` | **3.6.0**（新規） |
| flyway-core / flyway-database-postgresql | `org.flywaydb` | **12.1.0**（新規） |


## [2026.09] - 2026-06-15

> 変更: onigiri-parser 0.9.0 → **0.9.1**（with-bh,with-abr 同梱の完全 jar = ABR+BH 両機能入り）。他据え置き。
> 0.9.0 は with-bh のみビルドで ABR クラス欠落だったため差し替え。

| artifact | groupId | version |
|----------|---------|---------|
| unlaxer-common | `org.unlaxer` | 2.8.0 |
| building-hierarchy | `org.unlaxer` | 0.14.1 |
| abr-utils | `org.unlaxer.geo` | 0.10.1 |
| onigiri-parser | `org.unlaxer` | **0.9.1** |


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
