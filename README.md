# SIMトク速報

携帯各社の期間限定キャンペーンを紹介する静的サイトです。

- 記事は `content/*.md` に1本1ファイルで書きます（先頭の `---` の間に title / date / carrier / lead / tags / period / end / source）。
- `python3 build.py` を実行すると `docs/` にサイトが出力されます（外部ライブラリ不要）。
- `main` に push すると GitHub Actions がビルドして GitHub Pages に公開します（毎日0時にも再ビルドし、残り日数を更新）。
- `end` に終了日（YYYY-MM-DD）を入れると「あと◯日」バッジとサイドバーの「まもなく終了」に自動で反映されます。
