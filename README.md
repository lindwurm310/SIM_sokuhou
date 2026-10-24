# SIMトク速報

携帯各社の期間限定キャンペーンを紹介する静的サイトです。

- 記事は `content/*.md` に1本1ファイルで書きます（先頭の `---` の間に title / date / carrier / lead / tags / period / end / source）。
- `python3 build.py` を実行すると `docs/` にサイトが出力されます（外部ライブラリ不要）。
- Cloudflare Workers（静的アセット）で公開します。ビルドコマンド `python3 build.py`、デプロイコマンド `npx wrangler deploy`（設定は `wrangler.jsonc`）。`main` に push すると自動で再公開されます。
- 残り日数の表示を更新するため、GitHub Actions（`.github/workflows/daily-rebuild.yml`）が毎日0時（日本時間）に Cloudflare のデプロイフックを呼びます。フックのURLはリポジトリのシークレット `CLOUDFLARE_DEPLOY_HOOK` に登録してください。
- サムネイルは `image` に各社公式キャンペーンページの og:image のURLを入れ、`image_credit` に出典（例：ワイモバイル公式サイト）を書きます。ニュースサイトや比較サイトの画像は使いません。画像がない・読み込めない場合はキャリア色のカードが表示されます。
- サイドバーの「カテゴリ」は `tags` から自動で振り分けます（`build.py` の `CATEGORIES`）。使うタグ：MNP / 端末割引 / 一括1円 / iPhone / Android / 返却プログラム / 事務手数料無料 / ポイント還元 / 残高還元 / キャッシュバック / SIMのみ。
- サイドバーの「累計アクセスランキング」は、記事ページを開くと `/api/hit` に送られた閲覧数（同じ端末・同じ記事は1日1回）を `src/worker.js` の Durable Object（無料プランの範囲）に貯めて上位5件を出します。「あなたへのおすすめ」はブラウザに残した閲覧履歴から、同じキャリアや共通のタグの開催中キャンペーンを選びます（履歴がなければ新着順）。データは `docs/data/articles.json`（ビルド時に生成）。
- サイドバーの X へのリンクは `build.py` の `X_URL` にアカウントのURLを入れると表示されます。
- 右上のボタンでライト／ダークを切り替えられます（初期状態は端末の設定に合わせます）。
- `end` に終了日（YYYY-MM-DD）を入れると「あと◯日」バッジとサイドバーの「まもなく終了」に自動で反映されます。
- 乗り換え（MNP）の端末価格は、GitHub Actions（`.github/workflows/mnp-watch.yml`）が毎朝8時半（日本時間）にキャリア公式ページを確認し、価格の行が増えたり消えたりしたら Issue「MNP端末価格の変化」を立てます。記事はその Issue を見て書きます（自動で記事にはしません）。取得先は `watch/mnp_sources.json` に追加できます。robots.txt で禁止されているページ（ソフトバンクのオンラインショップのキャンペーンページなど）や量販店・比較サイトは入れないでください。前回の結果は Actions のキャッシュに置くので、7日以上動かないと消えて、次の回は「初めて取得しました」として今の価格が全部 Issue に出ます。
