# SIMトク速報

携帯各社の期間限定キャンペーンを紹介する静的サイトです。

- 記事は `content/*.md` に1本1ファイルで書きます（先頭の `---` の間に title / date / carrier / lead / tags / period / end / source）。
- `python3 build.py` を実行すると `docs/` にサイトが出力されます（外部ライブラリ不要）。
- Cloudflare Workers（静的アセット）で公開します。ビルドコマンド `python3 build.py`、デプロイコマンド `npx wrangler deploy`（設定は `wrangler.jsonc`）。`main` に push すると自動で再公開されます。
- 残り日数の表示を更新するため、GitHub Actions（`.github/workflows/daily-rebuild.yml`）が毎日0時（日本時間）に Cloudflare のデプロイフックを呼びます。フックのURLはリポジトリのシークレット `CLOUDFLARE_DEPLOY_HOOK` に登録してください。
- サムネイルは `image` に各社公式キャンペーンページの og:image のURLを入れ、`image_credit` に出典（例：ワイモバイル公式サイト）を書きます。ニュースサイトや比較サイトの画像は使いません。画像がない・読み込めない場合はキャリア色のカードが表示されます。
- サイドバーの「カテゴリ」は `tags` から自動で振り分けます（`build.py` の `CATEGORIES`）。使うタグ：MNP / 端末割引 / 一括1円 / iPhone / Android / 返却プログラム / 事務手数料無料 / ポイント還元 / 残高還元 / キャッシュバック / SIMのみ。
- 右上のボタンでライト／ダークを切り替えられます（初期状態は端末の設定に合わせます）。
- `end` に終了日（YYYY-MM-DD）を入れると「あと◯日」バッジとサイドバーの「まもなく終了」に自動で反映されます。
- 新しい記事（`content/*.md` の追加）が `main` に push されると、GitHub Actions（`.github/workflows/post-to-x.yml`）が記事ページの公開を待ってから次のことをします（`scripts/post_to_x.py`）。投稿文は `python3 scripts/post_to_x.py content/xxx.md` で手元でも確認できます。
  - **X（無料・半自動）**：「Xで投稿する」リンク入りの Issue を作ります。GitHub アプリの通知から開いてリンクをタップすると、投稿文が入った状態で X が開くので、確かめて投稿し、Issue を閉じます。
  - **Bluesky（無料・自動）**：変数 `BLUESKY_HANDLE`（例：simtoku.bsky.social）とシークレット `BLUESKY_APP_PASSWORD`（Bluesky の設定で作るアプリパスワード）を登録し、変数 `BLUESKY_POST_ENABLED` を `true` にすると自動で投稿します。
  - **X（有料・自動）**：X API のキー4つをシークレット `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` に登録し、変数 `X_POST_ENABLED` を `true` にすると自動で投稿します（このとき Issue は作りません）。URL入りは1件0.20ドル、変数 `X_INCLUDE_URL` を `false` にするとURLなしで1件0.015ドルです。
