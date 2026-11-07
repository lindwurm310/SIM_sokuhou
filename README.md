# SIMトク速報

携帯各社の期間限定キャンペーンを紹介する静的サイトです。

- 記事は `content/*.md` に1本1ファイルで書きます（先頭の `---` の間に title / date / carrier / lead / tags / period / end / source）。
- `python3 build.py` を実行すると `docs/` にサイトが出力されます（外部ライブラリ不要）。
- Cloudflare Workers（静的アセット）で公開します。独自ドメイン https://simsoku.com/（`build.py` の `SITE_URL`）。ビルドコマンド `python3 build.py`、デプロイコマンド `npx wrangler deploy`（設定は `wrangler.jsonc`）。`main` に push すると自動で再公開されます。
- 残り日数の表示を更新するため、GitHub Actions（`.github/workflows/daily-rebuild.yml`）が毎日0時（日本時間）に Cloudflare のデプロイフックを呼びます。フックのURLはリポジトリのシークレット `CLOUDFLARE_DEPLOY_HOOK` に登録してください。
- サムネイルは `image` に各社公式キャンペーンページの og:image のURLを入れ、`image_credit` に出典（例：ワイモバイル公式サイト）を書きます。ニュースサイトや比較サイトの画像は使いません。画像がない・読み込めない場合はキャリア色のカードが表示されます。
- サイドバーの「カテゴリ」は `tags` から自動で振り分けます（`build.py` の `CATEGORIES`）。使うタグ：MNP / 端末割引 / 一括1円 / iPhone / Android / 返却プログラム / 事務手数料無料 / ポイント還元 / 残高還元 / キャッシュバック / SIMのみ / AI / ガジェット（AIアシスタントやスマートスピーカーなど通信以外のサービス・機器の記事は「AI・ガジェット」に入り、`carrier` には `Amazon` のようにサービス名を書きます）。
- サイドバーの「累計アクセスランキング」は、記事ページを開くと `/api/hit` に送られた閲覧数（同じ端末・同じ記事は1日1回）を `src/worker.js` の Durable Object（無料プランの範囲）に貯めて上位5件を出します。「あなたへのおすすめ」はブラウザに残した閲覧履歴から、同じキャリアや共通のタグの開催中キャンペーンを選びます（履歴がなければ新着順）。データは `docs/data/articles.json`（ビルド時に生成）。
- サイドバーの「公式X」は `build.py` の `X_URL` にアカウントのURLを入れると表示されます。X 公式の埋め込みタイムラインで投稿内容を表示し（`static/sidebar.js` がスクロールで近づいたときに読み込む）、広告ブロッカーなどで読み込めない場合は最新記事3本の紹介ポストを一覧で表示します。
- 右上のボタンでライト／ダークを切り替えられます（初期状態は端末の設定に合わせます）。
- `end` に終了日（YYYY-MM-DD）を入れると「あと◯日」バッジとサイドバーの「まもなく終了」に自動で反映されます。
- SNS用のカード画像：記事ごとに 1200×630 の画像（タイトル・キャリア名・見どころ・終了日入り）を `static/ogp/<記事名>.png` に置き、記事ページの `og:image` / `twitter:image` に設定します。X や Bluesky、LINE で記事URLを共有すると大きな画像つきのカードになります。画像は `python3 scripts/make_ogp.py` で作れます（Pillow と日本語フォント Noto Sans CJK が必要）。記事を `main` に push すると、画像がない記事やタイトルを書き直した記事のぶんは GitHub Actions が自動で作ってコミットします。画像がない記事やトップページなどは `static/ogp/default.png` を使います。
- 新しい記事（`content/*.md` の追加）が `main` に push されると、GitHub Actions（`.github/workflows/post-to-x.yml`）が記事ページの公開を待ってから次のことをします（`scripts/post_to_x.py`）。投稿文は `python3 scripts/post_to_x.py content/xxx.md` で手元でも確認できます。
  - **X（無料・半自動）**：「Xで投稿する」リンク入りの Issue を作ります。GitHub アプリの通知から開いてリンクをタップすると、投稿文が入った状態で X が開くので、確かめて投稿し、Issue を閉じます。
  - **Bluesky（無料・自動）**：変数 `BLUESKY_HANDLE`（例：simtoku.bsky.social）とシークレット `BLUESKY_APP_PASSWORD`（Bluesky の設定で作るアプリパスワード）を登録し、変数 `BLUESKY_POST_ENABLED` を `true` にすると自動で投稿します。
  - **X（有料・自動）**：X API のキー4つをシークレット `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` に登録し、変数 `X_POST_ENABLED` を `true` にすると自動で投稿します（このとき Issue は作りません）。URL入りは1件0.20ドル、変数 `X_INCLUDE_URL` を `false` にするとURLなしで1件0.015ドルです。
- 広告（アフィリエイト）：`affiliates.json` のキャリアごとの `url` にASPの広告リンクを入れると、そのキャリアの記事とキャリア別ページに「PR」付きの申し込みボタンと、タイトル下の「プロモーションが含まれます」表記が自動で出ます（`url` が空なら何も出ません）。`label` はボタンの文言、`pixel` はASPの計測用画像（A8.net の `<img src="…">` の URL）です。記事ごとに止めたいときは前付けに `affiliate: off`、別のリンクを使いたいときは `affiliate_url: https://…` を書きます。
- X投稿の一言：前付けに `x_intro: 楽天モバイルでiPadが2万円引きになってるよ。` のように書くと、Xの投稿文の文頭に付きます（なければ「◯◯のおトクな情報だよ。」）。
- 固定ページ（運営者情報・プライバシーポリシー・広告掲載について・お問い合わせ）は `pages/*.md` から生成し、フッターにリンクします。
- 検索対策のタイトル：前付けに `seo_title:` を書くと、検索結果やタブに出るタイトル（`<title>`）だけをそれに替えます（記事の見出しやXの投稿文は `title` のまま）。検索されやすいよう「キャリア名＋サービス・端末名＋金額＋いつまで」を先頭30字くらいに入れます（例：`LINEMOの事務手数料0円は11月8日まで、乗り換えで最大1.2万円相当と併用OK`）。書かなければ `title` に終了日（【11月30日まで】）を足します（`title` に「まで」がないとき）。
- 構造化データ：記事ページに NewsArticle とパンくず、トップに WebSite、まとめページに ItemList の JSON-LD を自動で入れます（Google の検索結果や Discover 向け）。
- 関連記事：記事の下に「同じキャリアのほかの記事」と、タグが重なる他社の「あわせて読みたい」（開催中のものを優先して各4件）、まとめページへのリンクを自動で出します。
- 開催中まとめ：`campaigns.html` に、開催中のキャンペーン（終了日が今日以降、終了日がなければ公開から45日以内）をキャリア別・終了日順の表にまとめます。毎日の再ビルドで中身とタイトルの年月が更新されます。ナビの「開催中まとめ」からリンクしています。
- RSS：`feed.xml` に新しい20件を配信します（各ページの `<head>` とフッターにリンク）。
- アクセス解析・所有確認：`build.py` の `CF_BEACON_TOKEN`（Cloudflare Web Analytics のトークン）、`GOOGLE_SITE_VERIFICATION`（Search Console の HTML タグの値）、`BING_SITE_VERIFICATION` に値を入れると全ページにタグが入ります。空なら何も出しません。Search Console は DNS（Cloudflare）で確認してもかまいません。確認後、サイトマップ `https://simsoku.com/sitemap.xml` を送信します。
- 終了前日のリマインド：GitHub Actions（`.github/workflows/ending-reminder.yml`）が毎日18時（日本時間）に、翌日終わる記事の「明日まで」投稿文（`scripts/ending_soon.py`）を「Xで投稿する」リンク付きの Issue にします。`python3 scripts/ending_soon.py 1` で手元でも確認できます。
