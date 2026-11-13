#!/usr/bin/env python3
"""記事ごとの SNS 用画像（OGP画像、1200×630 の PNG）を static/ogp/<記事名>.png に作る。
あわせて、サイトのサムネイル用のアイキャッチ画像（960×540 の WebP）を static/thumb/<記事名>.webp に作る。
公式サイトの画像（image）がない記事や、公式画像が読み込めなかったときにこちらを表示する。

X や Bluesky、LINE などで記事URLを共有したときに、この画像が大きなカードで表示される。
記事タイトル・キャリア名・見どころ（thumb）・終了日を、キャリア色のカードに描く。

使い方:
  python3 scripts/make_ogp.py            まだ画像がない記事のぶんだけ作る（サイト共通の default.png も）
  python3 scripts/make_ogp.py --all      すべて作り直す
  python3 scripts/make_ogp.py content/2026-11-02-xxx.md [...]   指定した記事だけ作り直す

必要なもの: Pillow（pip install pillow）と日本語フォント Noto Sans CJK
（Ubuntu なら apt install fonts-noto-cjk）。フォントの場所は環境変数 OGP_FONT_BOLD / OGP_FONT_REGULAR でも指定できる。
"""
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import CARRIER_COLORS, DEFAULT_COLOR, SITE_DESC, SITE_HOST, SITE_NAME, parse_front_matter  # noqa: E402

from scripts.eyecatch import render_eyecatch  # noqa: E402

OUT_DIR = ROOT / "static" / "ogp"
THUMB_DIR = ROOT / "static" / "thumb"
W, H = 1200, 630
S = 2  # 2倍の大きさで描いてから縮小し、図形のふちをなめらかにする

FONT_CANDIDATES = {
    "bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
             "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
             "C:/Windows/Fonts/YuGothB.ttc"],
    "regular": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
                "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc",
                "C:/Windows/Fonts/YuGothM.ttc"],
}
TEXT = "#141414"
MUTED = "#6f6f6f"
ORANGE = "#c95f0a"
ORANGE_PALE = "#fff1e3"
GREEN_DARK = "#0c4a35"
# 行頭に来てはいけない文字（禁則処理）
NO_LINE_START = set("、。，．,.)）]］」』】〕〉》！？!?ー・：；:;ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ々…％%")


def font_path(kind):
    env = os.environ.get(f"OGP_FONT_{kind.upper()}")
    for p in ([env] if env else []) + FONT_CANDIDATES[kind]:
        if p and Path(p).exists():
            return p
    sys.exit(f"日本語フォントが見つかりません（{kind}）。fonts-noto-cjk を入れるか OGP_FONT_{kind.upper()} を指定してください")


_fonts = {}


def font(kind, size):
    key = (kind, size)
    if key not in _fonts:
        path = font_path(kind)
        # .ttc の中から日本語（JP）のフォントを選ぶ。Noto Sans CJK は JP が先頭
        _fonts[key] = ImageFont.truetype(path, size * S, index=0)
    return _fonts[key]


def text_width(draw, text, f):
    return draw.textlength(text, font=f)


def wrap(draw, text, f, max_width):
    """1文字ずつ詰めて折り返す。英単語は途中で切らず、行頭禁則文字は前の行に残す。"""
    tokens, buf = [], ""
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch in "-+.%/"):
            buf += ch
            continue
        if buf:
            tokens.append(buf)
            buf = ""
        tokens.append(ch)
    if buf:
        tokens.append(buf)

    lines, line = [], ""
    for tok in tokens:
        if line and text_width(draw, line + tok, f) > max_width and not (tok[0] in NO_LINE_START):
            lines.append(line.rstrip())
            line = tok.lstrip()
        else:
            line += tok
    if line:
        lines.append(line)
    return lines


def fit_title(draw, title, max_width, max_lines=3):
    for size in (64, 60, 56, 52, 48, 44):
        f = font("bold", size)
        lines = wrap(draw, title, f, max_width)
        if len(lines) <= max_lines:
            return f, size, lines
    f = font("bold", 44)
    lines = wrap(draw, title, f, max_width)[:max_lines]
    while text_width(draw, lines[-1] + "…", f) > max_width:
        lines[-1] = lines[-1][:-1]
    lines[-1] += "…"
    return f, 44, lines


def pill(draw, x, y, text, f, fill, color, pad_x=22, height=52):
    """角の丸いラベルを描いて、右端の x 座標を返す（座標は1倍のもの）。"""
    w = text_width(draw, text, f) / S + pad_x * 2
    draw.rounded_rectangle([x * S, y * S, (x + w) * S, (y + height) * S], radius=height * S // 2, fill=fill)
    draw.text(((x + pad_x) * S, (y + height / 2) * S), text, font=f, fill=color, anchor="lm")
    return x + w


def logo_icon(draw, x, y, h):
    """サイトのロゴ（稲妻のアイコン）をグラデーションで描く。favicon.svg と同じ形。"""
    scale = h / 48
    icon = Image.new("RGBA", (int(40 * scale * S) + 2, int(48 * scale * S) + 2), (0, 0, 0, 0))
    grad = Image.new("RGBA", icon.size)
    gd = ImageDraw.Draw(grad)
    a, b = (0xF0, 0x56, 0x7C), (0x6B, 0x5B, 0xC4)
    n = icon.size[0] + icon.size[1]
    for i in range(n):
        t = i / n
        c = tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3)) + (255,)
        gd.line([(i, 0), (0, i)], fill=c)
        gd.line([(i, 0), (i - icon.size[1], icon.size[1])], fill=c, width=2)
    mask = Image.new("L", icon.size, 0)
    md = ImageDraw.Draw(mask)
    k = scale * S
    md.rounded_rectangle([0, 1 * k, 39 * k, 47 * k], radius=8 * k, fill=255)
    md.polygon([(28 * k, 0), (40 * k, 0), (40 * k, 12 * k)], fill=0)  # 右上の角を斜めに落とす
    icon.paste(grad, (0, 0), mask)
    bolt = ImageDraw.Draw(icon)
    bolt.polygon([(23 * k, 8 * k), (11 * k, 27 * k), (19 * k, 27 * k), (16 * k, 40 * k),
                  (29 * k, 20 * k), (21 * k, 20 * k)], fill="white")
    draw._image.paste(icon, (int(x * S), int(y * S)), icon)


def footer(draw):
    """下の帯：ロゴとサイト名、ドメイン。"""
    draw.rectangle([0, 548 * S, W * S, H * S], fill=GREEN_DARK)
    logo_icon(draw, 64, 565, 48)
    draw.text((118 * S, 589 * S), SITE_NAME, font=font("bold", 34), fill="white", anchor="lm")
    draw.text(((W - 64) * S, 589 * S), SITE_HOST, font=font("regular", 26), fill="#cfe3da", anchor="rm")


def render_article(meta):
    carrier = meta.get("carrier", "")
    bg, fg = CARRIER_COLORS.get(carrier, DEFAULT_COLOR)
    img = Image.new("RGB", (W * S, H * S), bg)
    draw = ImageDraw.Draw(img)
    # 白いカード
    draw.rounded_rectangle([40 * S, 36 * S, (W - 40) * S, 512 * S], radius=28 * S, fill="white")
    # 上段：キャリア名と終了日
    x = 84
    if carrier:
        x = pill(draw, x, 72, carrier, font("bold", 28), fg, "white") + 14
    end = meta.get("end", "")
    if len(end) == 10:
        m, d = int(end[5:7]), int(end[8:10])
        pill(draw, x, 72, f"{m}/{d}まで", font("bold", 28), ORANGE_PALE, ORANGE)
    # タイトル（最大3行）
    has_point = bool(meta.get("thumb"))
    f, size, lines = fit_title(draw, meta["title"], (W - 84 * 2) * S, 3)
    line_h = size * 1.38
    y = 150 if has_point else 170
    for line in lines:
        draw.text((84 * S, (y + line_h / 2) * S), line, font=f, fill=TEXT, anchor="lm")
        y += line_h
    # 見どころ（thumb）をオレンジで大きく
    if has_point:
        pf = font("bold", 40)
        point = meta["thumb"]
        while text_width(draw, "▶ " + point, pf) > (W - 84 * 2 - 40) * S and len(point) > 1:
            point = point[:-2] + "…"
        tw = text_width(draw, "▶ " + point, pf) / S
        draw.rounded_rectangle([72 * S, 408 * S, (72 + tw + 32) * S, 480 * S], radius=14 * S, fill=ORANGE_PALE)
        draw.text((88 * S, 444 * S), "▶ " + point, font=pf, fill=ORANGE, anchor="lm")
    footer(draw)
    return img.resize((W, H), Image.LANCZOS)


def render_default():
    img = Image.new("RGB", (W * S, H * S), "#e7f5ee")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([40 * S, 36 * S, (W - 40) * S, 512 * S], radius=28 * S, fill="white")
    logo_icon(draw, 96, 120, 150)
    draw.text((250 * S, 200 * S), SITE_NAME, font=font("bold", 96), fill=TEXT, anchor="lm")
    f = font("regular", 30)
    for i, line in enumerate(wrap(draw, SITE_DESC, f, (W - 96 * 2) * S)[:2]):
        draw.text((96 * S, (370 + i * 48) * S), line, font=f, fill=MUTED, anchor="lm")
    footer(draw)
    return img.resize((W, H), Image.LANCZOS)


def save(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".webp":
        img.save(path, quality=82, method=6)
    else:
        img.save(path, optimize=True)
    print(f"作成: {path.relative_to(ROOT)}")


def main(args):
    force = "--all" in args
    files = [Path(a) for a in args if a.endswith(".md")]
    targets = files or sorted((ROOT / "content").glob("*.md"))
    if not files and (force or not (OUT_DIR / "default.png").exists()):
        save(render_default(), OUT_DIR / "default.png")
    for path in targets:
        out = OUT_DIR / f"{path.stem}.png"
        thumb = THUMB_DIR / f"{path.stem}.webp"
        redo = force or bool(files)
        if out.exists() and thumb.exists() and not redo:
            continue
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        meta["slug"] = path.stem
        if redo or not out.exists():
            save(render_article(meta), out)
        if redo or not thumb.exists():
            colors = CARRIER_COLORS.get(meta.get("carrier", ""), DEFAULT_COLOR)
            save(render_eyecatch(meta, colors, font, wrap, text_width, logo_icon), thumb)


if __name__ == "__main__":
    main(sys.argv[1:])
