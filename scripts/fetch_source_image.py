#!/usr/bin/env python3
"""記事の引用元（source の公式ページ）から og:image を探し、記事のサムネイルとカード画像に使えるか確かめる。

- image がない記事：source が各社の公式サイト（OFFICIAL_DOMAINS）なら、そのページの og:image を取りに行き、
  使える画像なら前付けに image / image_credit / image_size を書き足す。
- image はあるが image_size がない記事：その画像を確かめて image_size を書き足す。
- 使えない画像（読み込めない・小さい・縦長・サイトのトップと同じ共通画像）なら image_size は書かず、
  `image_check: ng` を書いて次からは調べない。カード画像は自動生成のもの（static/ogp/*.png）のまま。

image_size が入った記事だけ、build.py が記事ページの og:image（X などで共有したときのカード画像）に公式画像を使う。
画像は取り込まず、公式サイトのURLをそのまま参照する（ファイルとしてはコピーしない）。

使い方:
  python3 scripts/fetch_source_image.py              すべての記事を調べる
  python3 scripts/fetch_source_image.py content/x.md 指定した記事だけ
必要なもの: Pillow（pip install pillow）
"""
import html
import io
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# 画像を使ってよい公式サイト（ドメインの末尾で判定）と、出典の書き方。
# ニュースサイトや比較サイトの画像は使わない。
OFFICIAL_DOMAINS = {
    "docomo.ne.jp": "ドコモ公式サイト",
    "ahamo.com": "ahamo公式サイト",
    "au.com": "au公式サイト",
    "kddi.com": "KDDI公式サイト",
    "uqwimax.jp": "UQ mobile公式サイト",
    "uqmobile.jp": "UQ mobile公式サイト",
    "povo.jp": "povo公式サイト",
    "softbank.jp": "ソフトバンク公式サイト",
    "ymobile.jp": "ワイモバイル公式サイト",
    "linemo.jp": "LINEMO公式サイト",
    "rakuten.co.jp": "楽天公式サイト",
    "iijmio.jp": "IIJmio公式サイト",
    "mineo.jp": "mineo公式サイト",
    "unext.jp": "U-NEXT公式サイト",
    "nothing.tech": "Nothing公式サイト",
    "apple.com": "Apple公式サイト",
    "geo-online.co.jp": "ゲオ公式サイト",
}
UA = "Mozilla/5.0 (compatible; simsoku-bot/1.0; +https://simsoku.com/)"
MIN_WIDTH = 600
MIN_RATIO, MAX_RATIO = 1.3, 2.2  # 横長の画像だけ（X の大きいカードは 1.91:1）


def get(url, limit=8_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(limit), r.geturl()


def og_image_of(page_url):
    raw, final = get(page_url, 2_000_000)
    text = raw.decode("utf-8", "replace")
    for tag in re.findall(r"<meta\b[^>]*>", text, re.I):
        if re.search(r"""(?:property|name)\s*=\s*["'](?:og:image|og:image:url|twitter:image)["']""", tag, re.I):
            m = re.search(r"""content\s*=\s*["']([^"']+)["']""", tag, re.I)
            if m:
                return urljoin(final, html.unescape(m.group(1).strip()))
    return ""


def official_credit(url):
    host = (urlparse(url).hostname or "").lower()
    for domain, credit in OFFICIAL_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return credit
    return ""


def check_image(img_url, source):
    """使える画像なら 'WxH' を返す。使えなければ理由を返す（先頭に ng:）。"""
    try:
        top = og_image_of(f"{urlparse(source).scheme}://{urlparse(source).netloc}/") if source else ""
    except Exception:
        top = ""
    if top and top.split("?")[0] == img_url.split("?")[0]:
        return "ng: サイト共通の画像"
    try:
        data, _ = get(img_url)
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
    except Exception as e:
        return f"ng: 読み込めない（{e}）"
    if w < MIN_WIDTH or not (MIN_RATIO <= w / h <= MAX_RATIO):
        return f"ng: 大きさが合わない（{w}x{h}）"
    return f"{w}x{h}"


def add_fields(path, fields):
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    lines = fm.strip("\n").splitlines() + [f"{k}: {v}" for k, v in fields.items()]
    path.write_text("---\n" + "\n".join(lines) + "\n---" + body, encoding="utf-8")


def process(path):
    sys.path.insert(0, str(ROOT))
    from build import parse_front_matter

    meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
    if meta.get("image_size") or meta.get("image_check"):
        return
    source = meta.get("source", "")
    fields = {}
    image = meta.get("image", "")
    if not image:
        credit = official_credit(source)
        if not credit:
            return  # 出典が公式サイトでなければ画像は使わない
        try:
            image = og_image_of(source)
        except Exception as e:
            print(f"{path.name}: 出典ページを読み込めない（{e}）")
            return  # 一時的なエラーかもしれないので印は付けず、次回また調べる
        if not image:
            print(f"{path.name}: og:image なし")
            add_fields(path, {"image_check": "ng"})
            return
        fields = {"image": image, "image_credit": credit}
    result = check_image(image, source)
    if result.startswith("ng: 読み込めない"):
        print(f"{path.name}: {result} {image}")
        return  # 一時的なエラーかもしれないので印は付けず、次回また調べる
    if result.startswith("ng"):
        print(f"{path.name}: {result} {image}")
        add_fields(path, {"image_check": "ng"})
        return
    fields["image_size"] = result
    print(f"{path.name}: {result} {image}")
    add_fields(path, fields)


def main():
    paths = [Path(p) for p in sys.argv[1:]] or sorted((ROOT / "content").glob("*.md"))
    for p in paths:
        if p.exists():
            process(p)


if __name__ == "__main__":
    main()
