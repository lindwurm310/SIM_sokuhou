"""引用できる公式画像がない記事のための、目を引くサムネイル画像（アイキャッチ）を描く。

キャリア色のグラデーションに、光の放射・水玉・記事の中身に合ったイラスト（スマホ・コイン・
SIMカードなど）を重ね、見どころ（thumb）を白い大きな文字で載せる。
scripts/make_ogp.py から呼ばれ、static/thumb/<記事名>.webp に保存する。
"""
import math
import random
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 960, 540   # 出来上がりの大きさ（16:9）
S = 2             # 2倍で描いてから縮小する
YELLOW = (255, 214, 64)
INK = (20, 20, 20)


def _rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def pick_motif(meta):
    """記事の中身から、右側に大きく描くイラストを選ぶ。"""
    text = meta.get("title", "") + meta.get("thumb", "")
    tags = set(meta.get("tags", []))
    if meta.get("carrier") == "セキュリティ" or "セキュリティ" in tags or re.search("詐欺|乗っ取り|不正", text):
        return "shield"
    if re.search("iPad|タブレット", text):
        return "tablet"
    if "AI" in tags or ("ガジェット" in tags and not tags & {"ポイント還元", "残高還元"}):
        return "sparkle"
    if tags & {"端末割引", "一括1円", "返却プログラム"}:
        return "phone"
    if "キャッシュバック" in tags or re.search("キャッシュバック|円引き|割引|円〜|半額", text):
        return "yen"
    if tags & {"ポイント還元", "残高還元"} or re.search(r"pt|ポイント|還元|P還元", text):
        return "points"
    if "事務手数料無料" in tags or re.search("0円|無料", text):
        return "zero"
    if tags & {"iPhone", "Android"}:
        return "phone"
    if tags & {"SIMのみ", "MNP"}:
        return "sim"
    if tags & {"AI", "ガジェット"}:
        return "sparkle"
    return "gift"


# ---- イラスト（どれも 1 倍の座標で、中心 (cx, cy)・大きさ r を基準に描く） ----

def _phone(d, cx, cy, r, main, font):
    w, h = r * 1.05, r * 1.9
    x0, y0 = cx - w / 2, cy - h / 2
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=r * .2, fill=(255, 255, 255, 255))
    m = r * .07
    scr = [x0 + m, y0 + m, x0 + w - m, y0 + h - m]
    d.rounded_rectangle(scr, radius=r * .15, fill=_mix(main, (255, 255, 255), .82) + (255,))
    d.rounded_rectangle([cx - r * .16, y0 + m + r * .05, cx + r * .16, y0 + m + r * .13], radius=r * .05, fill=INK + (255,))
    # 画面の中のアプリ
    for i in range(3):
        for j in range(4):
            ax, ay = scr[0] + r * .14 + i * r * .27, scr[1] + r * .38 + j * r * .3
            col = [main, _mix(main, YELLOW, .7), _mix(main, (255, 255, 255), .45)][(i + j) % 3]
            d.rounded_rectangle([ax, ay, ax + r * .19, ay + r * .19], radius=r * .05, fill=col + (255,))
    # 値札
    tx, ty = cx + w * .18, cy + h * .22
    d.rounded_rectangle([tx - r * .55, ty - r * .26, tx + r * .55, ty + r * .26], radius=r * .1, fill=YELLOW + (255,))
    d.text((tx, ty), "SALE", font=font(int(r * .3)), fill=INK + (255,), anchor="mm")


def _tablet(d, cx, cy, r, main, font):
    w, h = r * 1.75, r * 2.2
    x0, y0 = cx - w / 2, cy - h / 2
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=r * .16, fill=(255, 255, 255, 255))
    m = r * .09
    d.rounded_rectangle([x0 + m, y0 + m, x0 + w - m, y0 + h - m], radius=r * .08,
                        fill=_mix(main, (255, 255, 255), .8) + (255,))
    d.ellipse([cx - r * .55, cy - r * .55, cx + r * .55, cy + r * .55], fill=main + (255,))
    d.text((cx, cy), "SALE", font=font(int(r * .32)), fill=(255, 255, 255, 255), anchor="mm")


def _coin(d, cx, cy, r, label, font, gold=(255, 200, 40), deep=(196, 128, 8)):
    d.ellipse([cx - r, cy - r + r * .14, cx + r, cy + r + r * .14], fill=deep + (255,))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=gold + (255,))
    d.ellipse([cx - r * .8, cy - r * .8, cx + r * .8, cy + r * .8], outline=deep + (255,), width=max(2, int(r * .07)))
    d.text((cx, cy + r * .02), label, font=font(int(r * 1.05)), fill=deep + (255,), anchor="mm")


def _coins(d, cx, cy, r, main, font, label):
    _coin(d, cx + r * .55, cy + r * .55, r * .62, label, font)
    _coin(d, cx - r * .62, cy + r * .35, r * .5, label, font)
    _coin(d, cx - r * .05, cy - r * .2, r * .85, label, font)


def _zero(d, cx, cy, r, main, font):
    # 値札の形
    w, h = r * 2.1, r * 1.25
    x0, y0 = cx - w / 2, cy - h / 2
    d.polygon([(x0, cy), (x0 + h * .45, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0 + h * .45, y0 + h)],
              fill=(255, 255, 255, 255))
    d.ellipse([x0 + h * .3, cy - r * .1, x0 + h * .3 + r * .2, cy + r * .1], fill=main + (255,))
    d.text((cx + r * .18, cy + r * .02), "0円", font=font(int(r * .75)), fill=main + (255,), anchor="mm")


def _sim(d, cx, cy, r, main, font):
    w, h = r * 1.55, r * 2.0
    x0, y0 = cx - w / 2, cy - h / 2
    c = r * .45
    d.polygon([(x0, y0), (x0 + w - c, y0), (x0 + w, y0 + c), (x0 + w, y0 + h), (x0, y0 + h)], fill=(255, 255, 255, 255))
    gx0, gy0, gx1, gy1 = cx - r * .45, cy - r * .2, cx + r * .45, cy + r * .55
    d.rounded_rectangle([gx0, gy0, gx1, gy1], radius=r * .1, fill=(240, 196, 72, 255))
    lw = max(2, int(r * .04))
    for t in (1 / 3, 2 / 3):
        d.line([gx0, gy0 + (gy1 - gy0) * t, gx1, gy0 + (gy1 - gy0) * t], fill=(190, 140, 30, 255), width=lw)
    d.line([cx, gy0, cx, gy1], fill=(190, 140, 30, 255), width=lw)
    d.text((cx, y0 + r * .38), "SIM", font=font(int(r * .32)), fill=main + (255,), anchor="mm")


def _star(d, cx, cy, r, fill):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * .3
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(pts, fill=fill)


def _sparkle(d, cx, cy, r, main, font):
    _star(d, cx - r * .15, cy, r * 1.1, (255, 255, 255, 255))
    _star(d, cx + r * .75, cy - r * .7, r * .45, YELLOW + (255,))
    _star(d, cx + r * .7, cy + r * .75, r * .3, (255, 255, 255, 255))


def _shield(d, cx, cy, r, main, font):
    pts = [(cx, cy - r * 1.05), (cx + r * .9, cy - r * .7), (cx + r * .82, cy + r * .2),
           (cx, cy + r * 1.05), (cx - r * .82, cy + r * .2), (cx - r * .9, cy - r * .7)]
    d.polygon(pts, fill=(255, 255, 255, 255))
    d.line([(cx - r * .42, cy), (cx - r * .1, cy + r * .32), (cx + r * .45, cy - r * .32)],
           fill=main + (255,), width=int(r * .2), joint="curve")


def _gift(d, cx, cy, r, main, font):
    bx0, bx1 = cx - r * .85, cx + r * .85
    d.rectangle([bx0, cy - r * .2, bx1, cy + r * .95], fill=(255, 255, 255, 255))
    d.rectangle([bx0 - r * .1, cy - r * .55, bx1 + r * .1, cy - r * .15], fill=(255, 255, 255, 255))
    d.rectangle([cx - r * .14, cy - r * .55, cx + r * .14, cy + r * .95], fill=YELLOW + (255,))
    d.ellipse([cx - r * .7, cy - r * 1.05, cx - r * .05, cy - r * .5], outline=YELLOW + (255,), width=int(r * .14))
    d.ellipse([cx + r * .05, cy - r * 1.05, cx + r * .7, cy - r * .5], outline=YELLOW + (255,), width=int(r * .14))


def draw_motif(layer_draw, motif, cx, cy, r, main, font):
    if motif == "phone":
        _phone(layer_draw, cx, cy, r * 1.15, main, font)
    elif motif == "tablet":
        _tablet(layer_draw, cx, cy, r * .8, main, font)
    elif motif == "yen":
        _coins(layer_draw, cx, cy, r, main, font, "¥")
    elif motif == "points":
        _coins(layer_draw, cx, cy, r, main, font, "P")
    elif motif == "zero":
        _zero(layer_draw, cx, cy, r, main, font)
    elif motif == "sim":
        _sim(layer_draw, cx, cy, r, main, font)
    elif motif == "sparkle":
        _sparkle(layer_draw, cx, cy, r, main, font)
    elif motif == "shield":
        _shield(layer_draw, cx, cy, r, main, font)
    else:
        _gift(layer_draw, cx, cy, r, main, font)


def wrap_words(d, text, f, max_w, wrap, text_width):
    """空白で区切られた語はなるべく途中で切らずに折り返す。語を切ったかどうかも返す。"""
    words = text.split()
    lines, line, split_word = [], "", False
    for w in words:
        cand = (line + " " + w) if line else w
        if text_width(d, cand, f) <= max_w:
            line = cand
            continue
        if line:
            lines.append(line)
        if text_width(d, w, f) <= max_w:
            line = w
        else:
            parts = wrap(d, w, f, max_w)
            split_word = True
            lines += parts[:-1]
            line = parts[-1]
    if line:
        lines.append(line)
    return lines, split_word


def render_eyecatch(meta, colors, font, wrap, text_width, logo_icon):
    """colors はキャリアの (薄い色, 濃い色)。font(kind, size) などは make_ogp.py のものを渡す。"""
    main = _rgb(colors[1])
    rnd = random.Random(meta.get("slug", meta.get("title", "")))
    WW, HH = W * S, H * S
    # 背景：キャリアの濃い色を明るい→暗いの斜めグラデーションに
    light, dark = _mix(main, (255, 255, 255), .12), _mix(main, (0, 0, 0), .38)
    gx = Image.linear_gradient("L").rotate(90).transpose(Image.FLIP_LEFT_RIGHT).resize((WW, HH))
    gy = Image.linear_gradient("L").resize((WW, HH))
    grad = ImageChops.add(gx, gy, scale=2)
    img = Image.composite(Image.new("RGB", (WW, HH), dark), Image.new("RGB", (WW, HH), light), grad).convert("RGBA")

    # 右側のイラストを中心にした光の放射
    cx, cy = WW * .76, HH * .5
    fx = Image.new("RGBA", (WW, HH), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fx)
    n = 18
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + math.pi / n
        R = WW
        fd.polygon([(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R),
                    (cx + math.cos(a1) * R, cy + math.sin(a1) * R)], fill=(255, 255, 255, 22))
    for rr, al in ((HH * .46, 40), (HH * .36, 45)):
        fd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 255, 255, al))
    # 水玉と紙ふぶき
    for _ in range(26):
        x, y, s = rnd.uniform(0, WW), rnd.uniform(0, HH), rnd.uniform(6, 22) * S
        col = rnd.choice([(255, 255, 255, 70), YELLOW + (150,), (255, 255, 255, 40)])
        if rnd.random() < .6:
            fd.ellipse([x - s / 2, y - s / 2, x + s / 2, y + s / 2], fill=col)
        else:
            fd.rounded_rectangle([x - s, y - s / 3, x + s, y + s / 3], radius=s / 3, fill=col)
    img = Image.alpha_composite(img, fx)

    # イラスト（少し傾けて、影をつける）
    motif = pick_motif(meta)
    size = int(HH * .78)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_motif(ImageDraw.Draw(layer), motif, size / 2, size / 2, size * .32, main,
               lambda px: font("bold", max(8, int(px / S))))
    layer = layer.rotate(rnd.choice([-9, -6, 6, 9]), resample=Image.BICUBIC)
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(layer.getchannel("A").point(lambda v: v * .35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14 * S))
    ox, oy = int(cx - size / 2), int(cy - size / 2)
    img.alpha_composite(shadow, (ox + 6 * S, oy + 14 * S))
    img.alpha_composite(layer, (ox, oy))

    # 左側の文字が読みやすいよう、左を少し暗くする
    veil = Image.linear_gradient("L").rotate(90).resize((WW, HH)).point(lambda v: int(v * .45))
    img = Image.composite(Image.new("RGBA", (WW, HH), _mix(main, (0, 0, 0), .55) + (255,)), img, veil)

    d = ImageDraw.Draw(img)
    pad = 48
    # キャリア名
    carrier = meta.get("carrier", "")
    y = 52
    if carrier:
        f = font("bold", 26)
        tw = text_width(d, carrier, f) / S
        d.rounded_rectangle([pad * S, y * S, (pad + tw + 40) * S, (y + 50) * S], radius=25 * S, fill="white")
        d.text(((pad + 20) * S, (y + 25) * S), carrier, font=f, fill=main, anchor="lm")

    # 見どころを大きく（左 6 割に収まるよう文字の大きさを選ぶ）
    point = meta.get("thumb") or meta.get("title", "")
    max_w = (W * .58 - pad) * S
    end = meta.get("end", "")
    ribbon = len(end) == 10 and not re.search("まで|終了", point)
    # 語を切らずに収まる大きさを優先し、小さくなりすぎるときだけ語の途中で折り返す
    whole = split = None
    for fs in (84, 76, 68, 60, 54, 48, 42):
        f = font("bold", fs)
        lines, cut = wrap_words(d, point, f, max_w, wrap, text_width)
        if len(lines) > 3:
            continue
        if not cut:
            whole = whole or (fs, f, lines)
            break
        split = split or (fs, f, lines)
    if whole and (whole[0] >= 68 or not split or split[0] <= whole[0]):
        fs, f, lines = whole
    elif split:
        fs, f, lines = split
    else:
        fs, f = 42, font("bold", 42)
        lines = wrap(d, point, f, max_w)[:3]
    lh = fs * 1.22
    total = lh * len(lines) + (70 if ribbon else 0)
    ty = 120 + (330 - total) / 2
    for line in lines:
        for dx, dy in ((0, 4), (0, 2)):
            d.text((pad * S + dx * S, (ty + lh / 2 + dy) * S), line, font=f, fill=_mix(main, (0, 0, 0), .6) + (150,),
                   anchor="lm")
        d.text((pad * S, (ty + lh / 2) * S), line, font=f, fill="white", anchor="lm")
        ty += lh

    # 終了日のリボン（見どころに日付が入っていなければ）
    if ribbon:
        label = f"{int(end[5:7])}/{int(end[8:10])}まで"
        f = font("bold", 30)
        tw = text_width(d, label, f) / S
        x0, y0 = pad, ty + 16
        d.polygon([(x0 * S, y0 * S), ((x0 + tw + 56) * S, y0 * S), ((x0 + tw + 40) * S, (y0 + 27) * S),
                   ((x0 + tw + 56) * S, (y0 + 54) * S), (x0 * S, (y0 + 54) * S)], fill=YELLOW)
        d.text(((x0 + 20) * S, (y0 + 27) * S), label, font=f, fill=INK, anchor="lm")

    # 右下にサイト名
    out = img.convert("RGB")
    od = ImageDraw.Draw(out)
    logo_icon(od, W - 228, H - 54, 30)
    od.text(((W - 190) * S, (H - 39) * S), "SIMトク速報", font=font("bold", 24), fill="white", anchor="lm")
    return out.resize((W, H), Image.LANCZOS)
