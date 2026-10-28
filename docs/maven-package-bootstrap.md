# 既存 Maven 成果物の初回公開

`Bootstrap Maven packages` は、レビュー済みの移行バンドルをこの repo の GitHub Packages に
公開する手動 workflow。通常の tag / release による公開とは別の、既存版の初回コピー用。
`caulis/vacant-dev-workspace#19` の段階的移行で使う。

## 設定と入力

- Repository Variable `PACKAGE_MIGRATION_ENABLED=true` の repo だけで動く。
  個人側では未設定にしておく。同じ YAML を両環境で使える。
- runner は `PUBLISH_RUNNER_LABELS`（未設定時は `ubuntu-latest`）。
- 認証は自 repo の `GITHUB_TOKEN`（`contents: write`, `packages: write`）だけ。
  個人 PAT と org の読み取り PAT は不要。他 repo の Packages への書き込みはしない。
  GitHub は push 権限を持つ token にのみ draft Release を返すため、この手動ジョブには
  `contents: write` が必要。コードは checkout するだけで、Release や Git 履歴は変更しない。
  checkout の Git 資格情報は保存しない。
- バンドルは `caulis/unlaxer-bom` の `scripts/prepare-package-bundle.py` で作成する。
  対象 repo を明示し、外部へ公開せず、この private repo の draft Release に
  `maven-bootstrap.zip` として保存する。Release tag は `maven-bootstrap-YYYY-MM-DD`。
  **draft のまま使う**。公開すると既存の release 用 workflow が反応する可能性がある。
- `release_tag` と、別途検証した `bundle_sha256` を入力する。

まず `publish=false`（既定）で実行する。ZIP 全体、対象 repo、GAV、ファイル一覧、元 POM、
各ファイルの SHA-256 とサイズ、POM の registry owner を検証した後、既存版を読み取って照合する。
すべて未公開か、すべて同一内容の場合だけ成功する。後者は再公開しない。
既存版との不一致や部分公開を検出すると、書き込みを始める前に失敗する。

同じ入力で `publish=true` にすると、未公開の座標を Maven deploy plugin で公開し、
直後に全ファイルを再取得してハッシュ一致を確認する。jar の再ビルドはしない。
同時実行は直列化する。途中で失敗した場合は状態を確認してから再実行する。
部分公開された版や既存の版を自動で削除・上書きする機能はない。

## 変更の単位と検証範囲

初回公開 workflow・スクリプト・テストは unlaxer-bom と4つの parser repo で同一内容にする。
単独 repo の token で完結させるため、private の別 repo から実行時にスクリプトを取得しない。
変更時はこの5 repo に同期する。

```bash
python3 -m unittest discover -s tests -p test_package_publisher.py -v
```

テストは入力の改変・誤った公開先・パス逸脱・既存版との衝突の拒否、dry-run、
同一版の再実行、公開後のハッシュ検証を含む。

この workflow の成功は、別 repo の読み取り権限や継続公開、vacant-service の
取得先切り替えを保証しない。それらは親 issue の別の受入条件として検証する。

revert は追加した PR の merge commit の revert と、必要なら
`PACKAGE_MIGRATION_ENABLED=false`。公開済み成果物は保持し、履歴や既存版は削除しない。
