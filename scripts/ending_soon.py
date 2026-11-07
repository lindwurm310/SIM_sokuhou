#!/usr/bin/env python3
"""終了が近いキャンペーン記事の「明日まで」リマインド投稿文を作る（外部ライブラリ不要）。

使い方: python3 scripts/ending_soon.py [日数]   （省略時は1＝明日終わるもの）
  X_INTENT_OUT にファイルのパスを入れると、「Xで投稿する」リンク入りの Markdown を書き出す
  （GitHub Actions はこれを Issue にしてスマホに通知する）。対象がなければ何も書き出さない。
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from build import CONTENT, jp_date, ogp_image, parse_front_matter, today  # noqa: E402
from post_to_x import MAX_WEIGHT, compose, intent_link, weight  # noqa: E402


def reminders(days=1):
    target = (today() + timedelta(days=days)).isoformat()
    when = {0: "今日", 1: "明日"}.get(days, f"{days}日後の")
    out = []
    for path in sorted(CONTENT.glob("*.md")):
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        if meta.get("end") != target:
            continue
        carrier = meta.get("carrier", "")
        # 文頭の一言を「明日まで」の呼びかけにする
        meta["x_intro"] = f"{carrier}のこのキャンペーン、{when}{jp_date(target)}で終わっちゃうよ。"
        text, url = compose(meta, path.stem)
        out.append((path, meta, text, url))
    return out


def main(argv):
    days = int(argv[0]) if argv else 1
    items = reminders(days)
    if not items:
        print("対象の記事はありません")
        return
    links = []
    for path, meta, text, url in items:
        print(f"--- {path.name}（{weight(text)}/{MAX_WEIGHT}）\n{text}\n")
        image = ogp_image(path.stem)
        links.append(f"### {meta['title']}\n\n**[▶ Xで投稿する]({intent_link(text)})**\n\n```\n{text}\n```\n\n"
                     f"![カード画像]({image})\n")
    out = os.environ.get("X_INTENT_OUT", "")
    if out:
        Path(out).write_text(
            "まもなく終わるキャンペーンのリマインド投稿です。リンクを開くと投稿文が入った状態で X が開くので、"
            "内容を確かめて投稿してください。投稿が済んだらこの Issue を閉じてください。\n\n" + "\n".join(links),
            encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
