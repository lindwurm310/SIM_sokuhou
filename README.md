# SIMトク速報

携帯各社の期間限定キャンペーンを紹介する静的サイトです。

- 記事は `content/*.md` に1本1ファイルで書きます（先頭の `---` の間に title / date / carrier / lead / tags / period / end / source）。
- `python3 build.py` を実行すると `docs/` にサイトが出力されます（外部ライブラリ不要）。
- Cloudflare Workers（静的アセット）で公開します。ビルドコマンド `python3 build.py`、デプロイコマンド `npx wrangler deploy`（設定は `wrangler.jsonc`）。`main` に push すると自動で再公開されます。
- 残り日数の表示を更新するため、GitHub Actions（`.github/workflows/daily-rebuild.yml`）が毎日0時（日本時間）に Cloudflare のデプロイフックを呼びます。フックのURLはリポジトリのシークレット `CLOUDFLARE_DEPLOY_HOOK` に登録してください。
- `end` に終了日（YYYY-MM-DD）を入れると「あと◯日」バッジとサイドバーの「まもなく終了」に自動で反映されます。
