# 同一 owner のソースを集約 registry へ公開する

`publish-sources.yml` は、同一 owner のソースを固定 commit からビルドし、実行元の `unlaxer-bom` registry へ公開する手動 workflow です。caulis 側では読み取りに管理アカウント、書き込みに **caulis/unlaxer-bom の GITHUB_TOKEN** を使います。既存の個人向け `publish.yml` は継続します。

Maven パッケージは紐付いた repository の権限で管理されるため、集約先で公開処理を実行します。新しい write PAT は不要です。書き込み先は実行中の repository、ソースと Maven の読み取り先はその owner です。個人側に同期した同じ YAML でも、その owner の設定を指定して実行できます。

## 対象

| source_repo | POM / artifact |
|---|---|
| unlaxer-bom | root / unlaxer-bom |
| japanese-parser-common | root / japanese-parser-common |
| building-hierarchy | root / building-hierarchy |
| municipality-history | root / municipality-history |
| historical-town-names | root / historical-town-names |
| japanpost-history | root / japanpost-history |
| onigiri-parser | root / onigiri-parser |
| ABRUtils | root / abr-utils、abr-api、abr-historical |
| kugiri | root / kugiri、building / kugiri-building |

ABR / kugiri の sibling POM は root reactor に含まれないため、明示的にビルドします。POM の GAV・依存 pin は変更しません。版はソースの明示値を使います。新しい版はソース repo で version bump してから公開してください。

`unlaxer-common:3.0.11` は公式 Maven Central の成果物を初回移行済みです。この workflow で別ソースから作り直しません。ikura / shake / okaka / kombu は各 repo の `publish.yml` にある自 repo 公開 job を使います。

## 設定

| Variable | caulis の値 |
|---|---|
| `PACKAGES_READ_SECRET_NAME` | `CAULIS_PACKAGES_READ_TOKEN` |
| `PACKAGES_READ_ACCOUNT` | `caulis-deployuser` |
| `LOCAL_SOURCE_PUBLISH_ENABLED` | 実公開を有効にするときだけ `true` |
| `PUBLISH_RUNNER_LABELS` | 未設定時は `["ubuntu-latest"]` |

選択した Secret の値を別の PAT で代替しません。`/user` API の login と指定アカウントの一致を検証し、caulis では `caulis-deployuser` を必須にします。org Secret の配布先には **unlaxer-bom**、管理アカウントの Read 対象には上表のソース repo と依存 Packages の repo が必要です。

Secret が未配布なら dry-run も失敗します。実公開が無効のまま `dry_run=false` を指定した場合も、スキップで成功扱いにはせずエラーにします。初回は配布確認と dry-run の成功後に有効化します。管理 Secret での実行・切替は `caulis/vacant-dev-workspace#19` で追跡し、準備 PR の CI 成功だけでは移行完了と扱いません。

## 手順

1. caulis の対象ソースの CI が成功した commit SHA（40桁）を選びます。onigiri-parser / ABRUtils の開発本流は **develop**、JPC は **master** です。GitHub default branch の古い POM を誤って選ばないでください。
2. `Publish source packages into BOM registry` を `source_repo` / `source_commit` / `dry_run=true` で実行します。GitHub Packages には書き込まず、空の Maven repository でテストして、一時 file:// registry に deploy します。
3. Actions artifact の `source-publish-report.json` と `staging/` で source SHA・GAV・POM の取得/公開先を確認します。レポートの SHA-256 は **一時 registry のファイル**に対する値です。
4. `LOCAL_SOURCE_PUBLISH_ENABLED=true` にして、同じ source SHA を `dry_run=false` で実行します。全対象のテストと一時 deploy が成功してから遠隔 deploy へ進みます。既存の個人向け公開は従来の workflow で実行できます。片方の公開経路がもう片方の PAT に依存することはありません。
5. caulis の消費側を空キャッシュでビルドし、公開後の依存解決を確認します。

既存 release の POM / jar が揃っている座標は再公開せず、`existingReleaseSkipped` に記録します。これは選択 commit と既存 jar の同一性を保証するものではありません。同じ版を別の HEAD から再生成・上書きすることはしません。POM / jar が片方だけ存在するときや認証エラーは停止します。`-SNAPSHOT` は Maven の通常の timestamp 付き公開を行います。

各 Maven 実行で独立した settings / local repository を使い、HOME を変更しません。settings は token 値ではなく環境変数参照を含み、artifact には含めません。公開中の通信障害などで一部だけ成功した場合は状態を調査し、自動削除・版の上書きは行いません。

この workflow は意図したソース版を明示する手動公開から開始します。版番号を変えない通常のソース更新を自動で release へ再公開しないためです。戻すときは有効化変数を `false` にし、この PR を revert できます。既存 Packages と個人向け workflow はそのまま利用できます。
