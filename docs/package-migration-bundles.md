# 公開済み Maven 成果物の移行準備

同じ版を現在のソースからビルドし直すと、本番と異なる jar を公開する可能性がある。
`scripts/prepare-package-bundle.py` は公開済み成果物を取得し、検証可能な ZIP と manifest を作る。
このスクリプト自身は registry への書き込みを行わない。

Python 3.11 以上、curl、元の GitHub Packages に対する読み取りトークンが必要。
トークンは既存の安全な方法で `GITHUB_PACKAGES_TOKEN` 環境変数に設定する。
コマンド引数やファイルには実値を渡さない。

```bash
python3 scripts/prepare-package-bundle.py \
  --coordinates config/package-migration/unlaxer-bom.json \
  --target-repository caulis/unlaxer-bom \
  --output /path/outside-checkout/unlaxer-bom.zip
```

他の4つの一覧も、ファイル名と同じ caulis repo を `--target-repository` に指定する。
対象と、未公開版・SNAPSHOT の扱いは [一覧の説明](../config/package-migration/README.md) を参照。

## 出力の確認

ZIP 内には次の3種類が入る。

- `manifest.json`: 対象 repo、GAV、packaging、各ファイルのパス・サイズ・SHA-256・取得元 URL。
- `artifacts/`: 公開用 POM と元のままの jar。存在する sources / javadoc も含む。
- `originals/`: URL 変更前の POM。manifest に元の SHA-256 を記録する。

ZIP と同名の `.json` は manifest に `bundleSha256` を加えたもの。
移送後はこのハッシュで ZIP 全体を検証し、公開前には各ファイルのハッシュと公開先を照合する。
POM の GAV は取得要求と一致することを検証する。Maven registry の owner と
`distributionManagement` の公開先だけを変更し、SCM URL・ライセンス・依存の版は維持する。

必須の POM / jar が取れない場合、GAV が違う場合、重複座標や SNAPSHOT がある場合は失敗する。
任意の sources / javadoc は 404 の場合だけ省略でき、401 / 403 は省略できない。
失敗時に部分 ZIP を残さず、既存 ZIP / manifest も上書きしない。

GitHub 認証は curl の標準入力に渡し、外部ホストへのリダイレクトに認証を転送しない。
Maven Central には認証を送らない。バンドルや manifest にトークンは入らない。
元の private 成果物を含むため、バンドルは private の移行先でのみ扱う。

## 検証

```bash
python3 -m unittest discover -s tests -v
```

テストは元 jar / POM の保持、URL の変換、ハッシュ、失敗時の部分成果物除去、
誤った GAV・パス・重複・上書きの拒否を確認する。
