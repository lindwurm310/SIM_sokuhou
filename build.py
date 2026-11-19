#!/usr/bin/env python3
"""content/*.md から docs/ に静的サイトを生成する（外部ライブラリ不要）。"""
import html
import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
PAGES = ROOT / "pages"
OUT = ROOT / "docs"
SITE_NAME = "SIMトク速報"
SITE_URL = "https://simsoku.com/"
# 旧URL（workers.dev）や www 付きで開かれたら、このホストの同じページへ転送する
SITE_HOST = "simsoku.com"
SITE_DESC = "携帯各社の期間限定キャンペーンを毎日チェックしてわかりやすく紹介"
# サイドバーに出す X（旧Twitter）アカウントのURL。空のままならリンク欄は出さない。
X_URL = "https://x.com/simsokuho"
# アクセス解析と検索エンジンの所有確認。空のままなら何も出さない。
# Cloudflare Web Analytics のトークン（ダッシュボード → Web Analytics → サイト追加 → JS スニペットの token の値）
CF_BEACON_TOKEN = "16f289ad429344ba9e167968f1fd3a9a"
# Google Search Console の「HTML タグ」で所有確認するときの content の値（DNS で確認するなら空のままでよい）
GOOGLE_SITE_VERIFICATION = ""
# Bing Webmaster Tools の所有確認（msvalidate.01 の content の値）
BING_SITE_VERIFICATION = ""
# 開催中キャンペーンのまとめページ
MATOME_PATH = "campaigns.html"
# 「今MNPするなら？」おすすめTOP5の固定ページ（中身は mnp_top5.json）
MNP_PATH = "mnp.html"
MNP_TOP5 = json.loads((ROOT / "mnp_top5.json").read_text(encoding="utf-8"))

# キャリアごとのサムネイル色（パステル）
CARRIER_COLORS = {
    "ドコモ": ("#ffd6dc", "#d2425a"),
    "ahamo": ("#d9f7ef", "#14866d"),
    "au": ("#ffe3cc", "#c25a12"),
    "UQ mobile": ("#dcecff", "#2c62b8"),
    "povo": ("#fff6c4", "#8a6d00"),
    "ソフトバンク": ("#e6e9ef", "#4a5160"),
    "ワイモバイル": ("#ffdcef", "#b8327a"),
    "LINEMO": ("#d8f5d8", "#2f8a3a"),
    "楽天モバイル": ("#f4dcff", "#8b2bb0"),
    "U-NEXT MOBILE": ("#dff1ff", "#1b5e8c"),
    "IIJmio": ("#ffe8d6", "#b4501a"),
    "mineo": ("#d6f5ee", "#0f7a66"),
    "Amazon": ("#e3f4ff", "#1f6f9e"),
    "セキュリティ": ("#ffe9e0", "#b23c17"),
    "ゲオモバイル": ("#dfe7ff", "#1f3f99"),
}
JST = timezone(timedelta(hours=9))

# キャリアごとの広告（アフィリエイト）リンク。url が空のキャリアには広告を出さない。
AFFILIATES = json.loads((ROOT / "affiliates.json").read_text(encoding="utf-8"))
PR_NOTE = '<p class="pr-note">{}にはプロモーションが含まれます</p>'
# A8.net のリンクマネージャー（提携中の広告主の公式サイトへのリンクを自動で広告リンクに置き換える）。
# 空にすると読み込まない。有効な間は、どの記事のリンクも広告になりうるので全記事に PR 表記を出す。
A8_LINKMGR_ID = "byVfdFBbOCiMYslBWooB"
# Google AdSense のサイト運営者ID（ca-pub-…）。空にすると読み込まず ads.txt も出さない。
ADSENSE_CLIENT = "ca-pub-2086077839254292"
# フッターに並べる固定ページ（pages/<slug>.md から生成）
FOOTER_PAGES = [("about", "運営者情報"), ("privacy", "プライバシーポリシー"),
                ("ad-policy", "広告掲載について"), ("contact", "お問い合わせ")]

# サイドバーのカテゴリ。記事の tags のどれかが含まれていればそのカテゴリに入る。
CATEGORIES = [
    ("mnp", "MNP（乗り換え）", {"MNP"}),
    ("device", "端末割引・一括1円", {"端末割引", "一括1円", "iPhone", "Android", "返却プログラム"}),
    ("fee", "事務手数料無料", {"事務手数料無料"}),
    ("point", "ポイント・残高還元", {"ポイント還元", "残高還元", "キャッシュバック"}),
    ("simonly", "SIMのみ契約", {"SIMのみ"}),
    ("gadget", "AI・ガジェット", {"AI", "ガジェット"}),
    ("security", "セキュリティ・注意喚起", {"セキュリティ"}),
]


def today():
    """ビルド環境のタイムゾーンに関係なく日本時間の日付を返す。"""
    return datetime.now(JST).date()


DEFAULT_COLOR = ("#e9e3ff", "#5b4bb7")
CARRIER_SLUGS = {
    "ドコモ": "docomo", "ahamo": "ahamo", "au": "au", "UQ mobile": "uqmobile", "povo": "povo",
    "ソフトバンク": "softbank", "ワイモバイル": "ymobile", "LINEMO": "linemo", "楽天モバイル": "rakuten",
    "U-NEXT MOBILE": "unext",
    "IIJmio": "iijmio",
    "mineo": "mineo",
    "Amazon": "amazon",
    "セキュリティ": "security",
    "ゲオモバイル": "geomobile",
}


def parse_front_matter(text):
    meta, body = {}, text
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        for line in fm.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    meta["tags"] = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    return meta, body.strip()


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[(.+?)\]\((https?://[^)\s]+)\)",
                  r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    return text


def markdown_to_html(md):
    """見出し・段落・箇条書き・表・注意ボックスだけを扱う小さな変換器。"""
    out, para, lines = [], [], md.splitlines()
    i = 0

    def flush():
        if para:
            out.append("<p>" + "<br>".join(inline(p) for p in para) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            flush()
        elif line.startswith("## "):
            flush()
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            flush()
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("> "):
            flush()
            box = []
            while i < len(lines) and lines[i].startswith("> "):
                box.append(inline(lines[i][2:]))
                i += 1
            out.append('<div class="note">' + "<br>".join(box) + "</div>")
            continue
        elif line.startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                           for r in rows[1:])
            out.append(f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
                       f"<tbody>{body}</tbody></table></div>")
            continue
        else:
            para.append(line)
        i += 1
    flush()
    return "\n".join(out)


def eyecatch_path(article):
    """scripts/make_ogp.py が作ったアイキャッチ画像（static/thumb/<記事名>.webp）のパス。なければ空。"""
    path = f"static/thumb/{article['slug']}.webp"
    return path if (ROOT / path).exists() else ""


def thumb(article, extra=""):
    """公式サイトの画像があれば使う。公式画像がない・読み込めないときは自動で作ったアイキャッチ画像を、
    それもなければキャリア色のカードを見せる。
    extra にクラス名（thumb-mini など）を渡すと、小さい一覧用の見た目にできる。"""
    bg, fg = CARRIER_COLORS.get(article["carrier"], DEFAULT_COLOR)
    label = html.escape(article.get("thumb", article["carrier"]))
    carrier = html.escape(article["carrier"])
    eye = eyecatch_path(article)
    eye_src = "{root}" + eye if eye else ""
    img = ""
    if article.get("image"):
        fallback = (f"this.onerror=null;this.src='{eye_src}';this.removeAttribute('referrerpolicy')"
                    if eye else "this.remove()")
        img = (f'<img class="thumb-img" src="{html.escape(article["image"])}" alt="" loading="lazy" '
               f'referrerpolicy="no-referrer" onerror="{fallback}">')
    elif eye:
        img = f'<img class="thumb-img" src="{eye_src}" alt="" loading="lazy" width="960" height="540">'
    cls = f"thumb {extra}".strip()
    return (f'<div class="{cls}" style="--tbg:{bg};--tfg:{fg}">'
            f'<span class="thumb-carrier">{carrier}</span>'
            f'<span class="thumb-label">{label}</span>{img}</div>')


def affiliate_for(carrier, article=None):
    """広告リンクを返す。記事の affiliate: off で止め、affiliate_url: で上書きできる。"""
    article = article or {}
    if article.get("affiliate") == "off":
        return None
    entry = AFFILIATES.get(carrier, {})
    url = article.get("affiliate_url") or entry.get("url", "")
    if not url.startswith("https://"):
        return None
    return {"url": url, "label": entry.get("label") or f"{carrier}の公式サイトで申し込む",
            "pixel": entry.get("pixel", "") if not article.get("affiliate_url") else ""}


def cta_box(aff):
    """PR ラベル付きの申し込みボタン。ASP の計測用画像（1x1）があれば添える。"""
    pixel = (f'<img class="cta-pixel" src="{html.escape(aff["pixel"])}" width="1" height="1" alt="">'
             if aff["pixel"].startswith("https://") else "")
    return (f'<div class="cta"><span class="pr-label">PR</span>'
            f'<a class="cta-button" href="{html.escape(aff["url"])}" target="_blank" rel="sponsored noopener">'
            f'{html.escape(aff["label"])}</a>{pixel}</div>')


def deadline_badge(article):
    end = article.get("end")
    if not end:
        return ""
    try:
        days = (date.fromisoformat(end) - today()).days
    except ValueError:
        return ""
    if days < 0:
        return '<span class="badge badge-ended">終了</span>'
    if days <= 7:
        return f'<span class="badge badge-soon">あと{days}日</span>'
    return f'<span class="badge">〜{end[5:].replace("-", "/")}</span>'


# SNS で共有したときのカード画像（scripts/make_ogp.py が static/ogp/ に作る 1200×630 の PNG）
DEFAULT_OGP = "static/ogp/default.png"


def page_url(path):
    """外から見える最終URL。Cloudflare は .html 付きのURLを拡張子なしへ 307 で飛ばすので、
    canonical / og:url / サイトマップ / SNSに載せるURLは最初から拡張子なしにそろえる。"""
    path = path[:-5] if path.endswith(".html") else path
    if path == "index" or path.endswith("/index"):
        path = path[:-5]
    return SITE_URL + path


def ogp_image(slug):
    """記事のカード画像のURL。まだ作っていなければサイト共通の画像にする。"""
    path = f"static/ogp/{slug}.png"
    return SITE_URL + (path if (ROOT / path).exists() else DEFAULT_OGP)


# X などで共有したときのカード画像に、引用元（各社公式ページ）の og:image を使うか。
# False にすると、すべての記事で自動生成のカード画像（static/ogp/*.png）に戻る。
OGP_USE_SOURCE_IMAGE = True


def card_image(article):
    """記事のカード画像（URL, 幅, 高さ）。scripts/fetch_source_image.py が確かめた公式画像
    （image_size が入っているもの）があればそれを、なければ自動生成のカード画像を使う。"""
    size = article.get("image_size", "")
    if OGP_USE_SOURCE_IMAGE and article.get("image") and re.fullmatch(r"\d+x\d+", size):
        w, h = size.split("x")
        return article["image"], w, h
    return ogp_image(article["slug"]), "1200", "630"


def json_ld(*items):
    """検索エンジン向けの構造化データ（JSON-LD）。"""
    return "".join('<script type="application/ld+json">'
                   + json.dumps(i, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"
                   for i in items)


def head_extras():
    out = []
    if GOOGLE_SITE_VERIFICATION:
        out.append(f'<meta name="google-site-verification" content="{html.escape(GOOGLE_SITE_VERIFICATION)}">')
    if BING_SITE_VERIFICATION:
        out.append(f'<meta name="msvalidate.01" content="{html.escape(BING_SITE_VERIFICATION)}">')
    return "\n".join(out)


def beacon():
    if not CF_BEACON_TOKEN:
        return ""
    return ("<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
            f"data-cf-beacon='{{\"token\": \"{html.escape(CF_BEACON_TOKEN)}\"}}'></script>")


def adsense():
    if not ADSENSE_CLIENT:
        return ""
    return ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            f'?client={html.escape(ADSENSE_CLIENT)}" crossorigin="anonymous"></script>')


def a8_linkmgr():
    if not A8_LINKMGR_ID:
        return ""
    return ('<script src="https://statics.8me.jp/a8link/a8linkmgr.js"></script>\n'
            f'<script>a8linkmgr({{"config_id": "{html.escape(A8_LINKMGR_ID)}"}});</script>')


def jp_date(d):
    """2026-11-30 → 11月30日"""
    return f"{int(d[5:7])}月{int(d[8:10])}日"


def seo_title(a):
    """検索結果に出るタイトル。前付けの seo_title: で上書きでき、なければ「いつまで」が分かるよう終了日を足す。"""
    if a.get("seo_title"):
        return a["seo_title"]
    t = a["title"]
    if a.get("end") and "まで" not in t and "終了" not in t:
        t += f"【{jp_date(a['end'])}まで】"
    return t


def is_open(a, on=None):
    """開催中か。終了日がなければ公開から45日以内を開催中とみなす。"""
    on = on or today()
    if a.get("end"):
        try:
            return date.fromisoformat(a["end"]) >= on
        except ValueError:
            return False
    return (on - date.fromisoformat(a["date"])).days <= 45


def iso_time(a):
    return f"{a['date']}T{a.get('time') or '00:00'}:00+09:00"


PUBLISHER = {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL,
             "logo": {"@type": "ImageObject", "url": SITE_URL + "static/favicon.svg"}}


def mnp_banner(path):
    """ヘッダー直下に出す「今MNPするなら？」の大きなバナー（TOP5ページ自身には出さない）。"""
    items = MNP_TOP5.get("items", [])
    if path == MNP_PATH or not items:
        return ""
    top = items[0]
    upd = MNP_TOP5["updated"]
    return (f'<div class="mnp-hero"><div class="wrap"><a class="mnp-hero-link" href="{{root}}{MNP_PATH}">'
            f'<span class="mnp-hero-kicker">毎日更新</span>'
            f'<span class="mnp-hero-title">今MNPするなら？</span>'
            f'<span class="mnp-hero-sub"><strong class="mnp-hero-mark">何度でも使えるキャンペーンだけ！</strong>維持費と還元のバランスで選んだ乗り換えおすすめTOP5</span>'
            f'<span class="mnp-hero-top">いま1位：{html.escape(top["carrier"])}「{html.escape(top["benefit"])}」'
            f'<span class="mnp-hero-date">{int(upd[5:7])}/{int(upd[8:10])}更新</span></span>'
            f'<span class="mnp-hero-cta">TOP5を見る →</span></a></div></div>')


def page(title, main, description=SITE_DESC, sidebar="", path="", image="", head="", image_size=("1200", "630")):
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{adsense()}
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{page_url(path)}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{page_url(path)}">
<meta property="og:type" content="{'article' if path.startswith('articles/') else 'website'}">
<meta property="og:image" content="{html.escape(image or SITE_URL + DEFAULT_OGP)}">
<meta property="og:image:width" content="{image_size[0]}">
<meta property="og:image:height" content="{image_size[1]}">
<meta property="og:image:alt" content="{html.escape(title)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{html.escape(image or SITE_URL + DEFAULT_OGP)}">
<meta name="twitter:site" content="@simsokuho">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME}" href="{SITE_URL}feed.xml">
{head_extras()}
{head}
<link rel="icon" href="{{root}}static/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap">
<link rel="stylesheet" href="{{root}}static/style.css">
<script>(function(h){{if(/\\.workers\\.dev$/.test(h)||h==="www.{SITE_HOST}")location.replace("https://{SITE_HOST}"+location.pathname+location.search+location.hash);}})(location.hostname);</script>
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}</script>
</head>
<body data-root="{{root}}" data-slug="{path[9:-5] if path.startswith('articles/') else ''}">
<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="{{root}}index.html" aria-label="{SITE_NAME} トップへ">
      <svg class="logo-icon" viewBox="0 0 40 48" aria-hidden="true">
        <defs><linearGradient id="logo-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" class="logo-stop-a"/><stop offset="1" class="logo-stop-b"/>
        </linearGradient></defs>
        <path d="M8 1h20l11 11v27a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8V9a8 8 0 0 1 8-8z" fill="url(#logo-grad)"/>
        <path class="logo-bolt" d="M23 8 11 27h8l-3 13 13-20h-8z"/>
      </svg>
      <span class="logo-text"><span class="logo-sim">SIM</span><span class="logo-toku">トク</span><span class="logo-news">速報</span></span>
    </a>
    <p class="tagline">{html.escape(SITE_DESC)}</p>
    <button class="theme-toggle" type="button" aria-label="ダークモード切り替え" onclick="toggleTheme()">
      <span class="icon-dark">🌙 ダーク</span><span class="icon-light">☀️ ライト</span>
    </button>
  </div>
  {mnp_banner(path)}
  <nav class="carrier-nav"><div class="wrap">{{nav}}</div></nav>
</header>
<div class="wrap layout">
  <main>{main}</main>
  <aside class="sidebar">{sidebar}</aside>
</div>
<footer class="site-footer"><div class="wrap">
  <p>掲載内容は記事公開時点の情報です。最新の条件は必ず各社公式サイトでご確認ください。</p>
  <p class="footer-links">{"".join(f'<a href="{{root}}{slug}.html">{name}</a>' for slug, name in FOOTER_PAGES)}<a href="{SITE_URL}feed.xml">RSS</a></p>
  <p>&copy; {today().year} {SITE_NAME}</p>
</div></footer>
<script>
function toggleTheme() {{
  var root = document.documentElement;
  var dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  try {{ localStorage.setItem("theme", root.dataset.theme); }} catch (e) {{}}
}}
</script>
<script src="{{root}}static/sidebar.js" defer></script>
{beacon()}
{a8_linkmgr()}
</body>
</html>"""


# サイト内リンク（相対パスか https://simsoku.com/ で始まるもの）の .html を外す。
# Cloudflare は .html 付きURLを拡張子なしへ 307 で飛ばすので、内部リンクも canonical と同じ
# 拡張子なしのURLにそろえ、Google が .html 版を「代替ページ」として拾わないようにする。
INTERNAL_HTML_LINK = re.compile(r'href="((?:' + re.escape(SITE_URL) + r'|(?![a-zA-Z][a-zA-Z0-9+.-]*:|//))[^"#?]*?)\.html(?=[#?"])')


def clean_link(m):
    path = m.group(1)
    if path == "index" or path.endswith("/index"):
        path = path[:-5]
    return f'href="{path or "./"}'


def render(template, root, nav):
    return INTERNAL_HTML_LINK.sub(clean_link, template.replace("{root}", root).replace("{nav}", nav))


def x_recent_posts(articles, handle, limit=3):
    """X の埋め込みが読み込めないとき用の、最近の投稿（記事紹介ポスト）の一覧。"""
    items = []
    for a in articles[:limit]:
        head = f"【{a['carrier']}】" if a.get("carrier") and not a["title"].startswith(a["carrier"]) else ""
        point = f"<br>▶ {html.escape(a['thumb'])}" if a.get("thumb") else ""
        items.append(
            f'<li class="x-post"><p class="x-post-head"><span class="x-post-name">{SITE_NAME}</span>'
            f'<span class="x-post-id">@{html.escape(handle)} · {int(a["date"][5:7])}月{int(a["date"][8:10])}日</span></p>'
            f'<p class="x-post-text">{html.escape(head + a["title"])}{point}</p>'
            f'<a class="x-post-link" href="{{root}}articles/{a["slug"]}.html">記事を読む</a></li>')
    return f'<ul class="x-posts">{"".join(items)}</ul>'


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "articles").mkdir(parents=True)
    (OUT / "carrier").mkdir()
    (OUT / "category").mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")

    articles = []
    for path in CONTENT.glob("*.md"):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        meta["slug"] = path.stem
        meta["body"] = markdown_to_html(body)
        articles.append(meta)
    articles.sort(key=lambda a: (a["date"], a.get("time", "")), reverse=True)

    # サイドバーのランキング・おすすめ用の記事データ（新しい順）
    (OUT / "data").mkdir()
    (OUT / "data" / "articles.json").write_text(json.dumps([
        {"slug": a["slug"], "title": a["title"], "carrier": a["carrier"], "tags": a["tags"], "end": a.get("end", ""),
         "thumb": a.get("thumb", a["carrier"]), "image": a.get("image", ""), "eyecatch": eyecatch_path(a),
         "bg": CARRIER_COLORS.get(a["carrier"], DEFAULT_COLOR)[0], "fg": CARRIER_COLORS.get(a["carrier"], DEFAULT_COLOR)[1]}
        for a in articles], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    carriers = sorted({a["carrier"] for a in articles},
                      key=lambda c: list(CARRIER_COLORS).index(c) if c in CARRIER_COLORS else 99)
    slug_of = {c: CARRIER_SLUGS.get(c, f"carrier{i}") for i, c in enumerate(carriers)}

    def nav(root, current=None):
        # current: "all"（トップ）か、キャリア名（キャリア別ページ・記事ページ）。該当するリンクを色付きにする
        def cur(key):
            return ' class="is-current" aria-current="page"' if key == current else ""
        links = [f'<a href="{root}index.html"{cur("all")}>すべて</a>',
                 f'<a href="{root}{MNP_PATH}"{cur("mnp")}>今MNPするなら？</a>',
                 f'<a href="{root}{MATOME_PATH}"{cur("matome")}>開催中まとめ</a>']
        links += [f'<a href="{root}carrier/{slug_of[c]}.html"{cur(c)}>{html.escape(c)}</a>' for c in carriers]
        return "".join(links)

    def card(a, root):
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in a["tags"])
        return f"""<article class="card">
  <a class="card-link" href="{root}articles/{a['slug']}.html">
    {thumb(a)}
    <div class="card-body">
      <h2 class="card-title">{html.escape(a['title'])}</h2>
      <p class="card-meta"><time>{a['date'].replace('-', '/')} {a.get('time', '')}</time>{deadline_badge(a)}</p>
      <p class="card-lead">{html.escape(a['lead'])}</p>
      <p class="card-tags">{tags}</p>
    </div>
  </a>
</article>"""

    def list_main(items, heading, root, intro=""):
        groups, out = {}, [f'<h1 class="list-heading">{heading}</h1>', intro]
        for a in items:
            groups.setdefault(a["date"], []).append(a)
        for d, group in groups.items():
            y, m, dd = d.split("-")
            out.append(f'<h2 class="date-heading">{int(y)}年{int(m)}月{int(dd)}日の記事</h2>')
            out += [card(a, root) for a in group]
        return "\n".join(out)

    def in_category(tags):
        return [a for a in articles if tags & set(a["tags"])]

    def related(a, limit=4):
        """同じキャリアの記事と、タグが重なる他社の記事。開催中のものを優先する。"""
        others = [b for b in articles if b["slug"] != a["slug"]]
        same = sorted((b for b in others if b["carrier"] == a["carrier"]),
                      key=lambda b: (not is_open(b), articles.index(b)))[:limit]
        shown = {b["slug"] for b in same}
        mine = set(a["tags"])
        near = sorted((b for b in others if b["slug"] not in shown and b["carrier"] != a["carrier"]
                       and mine & set(b["tags"])),
                      key=lambda b: (not is_open(b), -len(mine & set(b["tags"])), articles.index(b)))[:limit]
        return same, near

    def mini_list(items, root):
        rows = []
        for b in items:
            bg, fg = CARRIER_COLORS.get(b["carrier"], DEFAULT_COLOR)
            rows.append(f'<li><a href="{root}articles/{b["slug"]}.html">{thumb(b, "thumb-mini")}<span class="mini-text">'
                        f'<span class="mini-carrier" style="--tbg:{bg};--tfg:{fg}">{html.escape(b["carrier"])}</span>'
                        f'<span class="mini-title">{html.escape(b["title"])}</span>{deadline_badge(b)}</span></a></li>')
        return f'<ul class="mini-list">{"".join(rows)}</ul>'

    def related_html(a):
        same, near = related(a)
        out = []
        if same:
            out.append(f'<section class="related"><h2>{html.escape(a["carrier"])}のほかの記事</h2>{mini_list(same, "../")}'
                       f'<p class="related-more"><a href="../carrier/{slug_of[a["carrier"]]}.html">'
                       f'{html.escape(a["carrier"])}の記事をすべて見る →</a></p></section>')
        if near:
            out.append(f'<section class="related"><h2>あわせて読みたい</h2>{mini_list(near, "../")}</section>')
        out.append(f'<p class="related-more related-matome"><a href="../{MATOME_PATH}">'
                   f'いま開催中のキャンペーンまとめを見る →</a></p>')
        return "\n".join(out)

    handle = X_URL.rstrip("/").rsplit("/", 1)[-1]
    # X の投稿タイムライン（X 公式の埋め込み）。static/sidebar.js が近くまでスクロールしたときに読み込み、
    # 読み込めない環境（広告ブロッカーや、X 側で表示されない場合など）では最近の投稿一覧をそのまま見せる。
    x_box = (f'<section class="side-box side-x" id="side-x"><h2>公式X</h2>'
             f'<div class="x-timeline" data-href="https://twitter.com/{html.escape(handle)}">'
             f'{x_recent_posts(articles, handle)}</div>'
             f'<a class="x-follow" href="{html.escape(X_URL)}" target="_blank" rel="noopener">'
             f'<span class="x-logo" aria-hidden="true">𝕏</span>@{html.escape(handle)} をフォロー</a></section>'
             if X_URL else "")
    # 中身は static/sidebar.js が埋める
    ranking_box = ('<section class="side-box side-peach" id="side-ranking"><h2>累計アクセスランキング</h2>'
                   '<ol class="side-ranking"><li class="side-empty">読み込み中…</li></ol></section>')
    recommend_box = ('<section class="side-box side-sky" id="side-recommend"><h2>あなたへのおすすめ</h2>'
                     '<p class="side-note"></p><ul class="side-picks"><li class="side-empty">読み込み中…</li></ul></section>')

    def sidebar(root):
        soon = [a for a in articles if a.get("end") and 0 <= (date.fromisoformat(a["end"]) - today()).days <= 14]
        soon.sort(key=lambda a: a["end"])
        items = "".join(
            f'<li class="side-item"><a href="{root}articles/{a["slug"]}.html">{thumb(a, "thumb-mini")}'
            f'<span class="side-text">{html.escape(a["title"])}'
            f'<span class="side-date">{a["end"][5:].replace("-", "/")}まで</span></span></a></li>' for a in soon
        ) or "<li>2週間以内に終わるキャンペーンはありません</li>"
        cs = "".join(f'<li><a href="{root}carrier/{slug_of[c]}.html">{html.escape(c)}</a></li>' for c in carriers)
        cats = "".join(
            f'<li><a href="{root}category/{slug}.html">{html.escape(name)}'
            f'<span class="count">{len(in_category(tags))}</span></a></li>'
            for slug, name, tags in CATEGORIES if in_category(tags))
        return (f'<section class="side-box side-pink"><h2>まもなく終了</h2><ul>{items}</ul></section>'
                + recommend_box + x_box + ranking_box +
                f'<section class="side-box side-lavender"><h2>カテゴリ</h2><ul class="side-categories">{cats}</ul></section>'
                f'<section class="side-box side-mint"><h2>キャリア・サービス別</h2><ul class="side-carriers">{cs}</ul></section>')

    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL,
               "description": SITE_DESC, "inLanguage": "ja", "publisher": PUBLISHER}
    index = page(SITE_NAME, list_main(articles, "新着キャンペーン", ""), sidebar=sidebar(""), path="",
                 head=json_ld(site_ld))
    (OUT / "index.html").write_text(render(index, "", nav("", "all")), encoding="utf-8")

    for c in carriers:
        items = [a for a in articles if a["carrier"] == c]
        aff = affiliate_for(c)
        intro = PR_NOTE.format("このページ") + cta_box(aff) if aff else ""
        p = page(f"{c}のキャンペーン | {SITE_NAME}", list_main(items, f"{html.escape(c)}のキャンペーン", "../", intro),
                 sidebar=sidebar("../"), path=f"carrier/{slug_of[c]}.html")
        (OUT / "carrier" / f"{slug_of[c]}.html").write_text(render(p, "../", nav("../", c)), encoding="utf-8")

    for slug, name, tags in CATEGORIES:
        items = in_category(tags)
        if not items:
            continue
        p = page(f"{name}のキャンペーン | {SITE_NAME}", list_main(items, f"{html.escape(name)}のキャンペーン", "../"),
                 sidebar=sidebar("../"), path=f"category/{slug}.html")
        (OUT / "category" / f"{slug}.html").write_text(render(p, "../", nav("../")), encoding="utf-8")

    for a in articles:
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in a["tags"])
        period = f'<p class="period">キャンペーン期間：{html.escape(a["period"])}</p>' if a.get("period") else ""
        source = (f'<p class="source">公式情報：<a href="{html.escape(a["source"])}" target="_blank" rel="noopener">'
                  f'{html.escape(a["source"])}</a></p>') if a.get("source") else ""
        credit = (f'<p class="credit">画像：{html.escape(a["image_credit"])}</p>'
                  if a.get("image") and a.get("image_credit") else "")
        aff = affiliate_for(a["carrier"], a)
        main_html = f"""<article class="article">
  <p class="article-meta"><time>{a['date'].replace('-', '/')} {a.get('time', '')}</time>{deadline_badge(a)}</p>
  <h1 class="article-title">{html.escape(a['title'])}</h1>
  {PR_NOTE.format("本記事") if aff or A8_LINKMGR_ID else ""}
  <p class="card-tags">{tags}</p>
  {thumb(a).replace('class="thumb"', 'class="thumb thumb-large"')}
  {credit}
  {period}
  <div class="article-body">{a['body']}</div>
  {cta_box(aff) if aff else ""}
  {source}
  {related_html(a)}
  <p class="back"><a href="../index.html">← 記事一覧へ戻る</a></p>
</article>"""
        url = page_url(f"articles/{a['slug']}")
        article_ld = {
            "@context": "https://schema.org", "@type": "NewsArticle",
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "headline": a["title"], "description": a["lead"],
            "image": list(dict.fromkeys([card_image(a)[0], ogp_image(a["slug"])] + ([a["image"]] if a.get("image") else []))),
            "datePublished": iso_time(a), "dateModified": a.get("updated") and f"{a['updated']}T00:00:00+09:00" or iso_time(a),
            "author": {"@type": "Organization", "name": f"{SITE_NAME}編集部", "url": page_url("about")},
            "publisher": PUBLISHER, "keywords": ", ".join([a["carrier"]] + a["tags"]), "inLanguage": "ja",
        }
        crumbs = [("トップ", SITE_URL), (a["carrier"], page_url(f"carrier/{slug_of[a['carrier']]}")),
                  (a["title"], url)]
        crumb_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]}
        card, cw, ch = card_image(a)
        p = page(f"{seo_title(a)} | {SITE_NAME}", main_html, a["lead"], sidebar("../"),
                 path=f"articles/{a['slug']}.html", image=card, head=json_ld(article_ld, crumb_ld),
                 image_size=(cw, ch))
        (OUT / "articles" / f"{a['slug']}.html").write_text(render(p, "../", nav("../")), encoding="utf-8")

    for path in sorted(PAGES.glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        main_html = (f'<article class="article static-page"><h1 class="article-title">{html.escape(meta["title"])}</h1>'
                     f'<div class="article-body">{markdown_to_html(body)}</div></article>')
        p = page(f"{meta['title']} | {SITE_NAME}", main_html, meta.get("description", SITE_DESC),
                 sidebar(""), path=f"{path.stem}.html")
        (OUT / f"{path.stem}.html").write_text(render(p, "", nav("")), encoding="utf-8")

    # 開催中キャンペーンのまとめ（毎日の再ビルドで中身と日付が更新される）
    now = today()
    open_items = [a for a in articles if is_open(a, now)]
    soon = sorted((a for a in open_items if a.get("end") and (date.fromisoformat(a["end"]) - now).days <= 7),
                  key=lambda a: a["end"])

    def matome_table(items):
        rows = "".join(
            f'<tr><td><a href="articles/{a["slug"]}.html">{html.escape(a["title"])}</a></td>'
            f'<td class="nowrap">{jp_date(a["end"]) + "まで" if a.get("end") else "未定"}</td></tr>'
            for a in items)
        return ('<div class="table-wrap"><table class="matome-table"><thead><tr><th>キャンペーン</th><th>終了日</th>'
                f'</tr></thead><tbody>{rows}</tbody></table></div>')

    sections = []
    if soon:
        sections.append(f'<h2 id="soon">まもなく終了（7日以内）</h2>{matome_table(soon)}')
    toc = []
    for c in carriers:
        items = [a for a in open_items if a["carrier"] == c]
        if not items:
            continue
        items.sort(key=lambda a: (a.get("end") or "9999", a["date"]))
        toc.append(f'<a href="#c-{slug_of[c]}">{html.escape(c)}（{len(items)}）</a>')
        sections.append(f'<h2 id="c-{slug_of[c]}">{html.escape(c)}のキャンペーン</h2>{matome_table(items)}'
                        f'<p class="related-more"><a href="carrier/{slug_of[c]}.html">{html.escape(c)}の記事一覧 →</a></p>')
    matome_title = f"【{now.year}年{now.month}月】開催中のSIM・スマホのキャンペーンまとめ"
    matome_desc = (f"{now.month}月{now.day}日時点で開催中の携帯各社のキャンペーン{len(open_items)}件を、"
                   "キャリア別・終了日順にまとめました。乗り換え（MNP）特典、端末割引、ポイント還元を毎日更新しています。")
    matome_main = (f'<article class="article matome"><h1 class="article-title">{matome_title}</h1>'
                   f'<p class="article-meta"><time datetime="{now.isoformat()}">{now.year}/{now.month}/{now.day} 更新</time></p>'
                   f'<p>{html.escape(matome_desc)}終了日が近い順に並べています。条件は必ず各社の公式サイトで確認してください。</p>'
                   f'<nav class="matome-toc">{"".join(toc)}</nav>'
                   f'<div class="article-body">{"".join(sections)}</div></article>')
    matome_ld = {"@context": "https://schema.org", "@type": "ItemList", "name": matome_title,
                 "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": page_url(f"articles/{a['slug']}")}
                                     for i, a in enumerate(open_items)]}
    p = page(f"{matome_title} | {SITE_NAME}", matome_main, matome_desc, sidebar(""), path=MATOME_PATH,
             head=json_ld(matome_ld))
    (OUT / MATOME_PATH).write_text(render(p, "", nav("", "matome")), encoding="utf-8")

    # 「今MNPするなら？」おすすめTOP5（mnp_top5.json の順に1位〜5位）
    slugs = {a["slug"] for a in articles}
    upd = MNP_TOP5["updated"]
    mnp_title = f"今MNPするなら？乗り換えおすすめTOP5【{int(upd[:4])}年{int(upd[5:7])}月】"
    mnp_desc = ("いま他社から乗り換える（MNP）ならどこがおトク？キャッシュバックや割引の大きさだけでなく、"
                "毎月の維持費とのバランスで選んだおすすめキャンペーンを5つに絞って毎日見直しています。")
    ranks = []
    for i, it in enumerate(MNP_TOP5["items"][:5], 1):
        bg, fg = CARRIER_COLORS.get(it["carrier"], DEFAULT_COLOR)
        lis = "".join(f"<li>{inline(x)}</li>" for x in it.get("points", []))
        links = []
        if it.get("article") in slugs:
            links.append(f'<a href="articles/{it["article"]}.html">くわしい記事を読む →</a>')
        if it.get("source"):
            links.append(f'<a href="{html.escape(it["source"])}" target="_blank" rel="noopener">公式サイトで確認</a>')
        aff = affiliate_for(it["carrier"])
        ranks.append(
            f'<section class="mnp-rank" id="rank{i}" style="--tbg:{bg};--tfg:{fg}">'
            f'<div class="mnp-rank-head"><span class="mnp-rank-no">{i}<small>位</small></span>'
            f'<span class="mnp-rank-brand">{html.escape(it["carrier"])}</span>'
            f'<span class="tag">{html.escape(it.get("type", ""))}</span>{deadline_badge(it)}</div>'
            + (f'<figure class="mnp-rank-img"><img src="{html.escape(it["image"])}" alt="{html.escape(it["carrier"])}" '
               f'loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.remove()">'
               + (f'<figcaption>画像：{html.escape(it["image_credit"])}</figcaption>' if it.get("image_credit") else "")
               + '</figure>' if it.get("image") else "")
            + f'<h2 class="mnp-rank-benefit">{html.escape(it["benefit"])}</h2>'
            f'<p class="mnp-rank-name">{html.escape(it["name"])}</p>'
            f'<p>{inline(it.get("summary", ""))}</p>'
            + (f'<dl class="mnp-cost"><div><dt>対象プラン</dt><dd>{html.escape(it["plan"])}</dd></div>'
               f'<div><dt>月額の目安</dt><dd>{html.escape(it.get("monthly", ""))}</dd></div>'
               + (f'<div class="mnp-cost-year"><dt>1年間の実質負担</dt><dd>{it["cost_year"]:,}円'
                  f'<small>（月あたり約{round(it["cost_year"] / 12):,}円）</small></dd></div>'
                  if it.get("cost_year") else "")
               + '</dl>' if it.get("plan") else "")
            + (f'<ul>{lis}</ul>' if lis else "")
            + (f'<p class="mnp-rank-for">こんな人におすすめ：{html.escape(it["for"])}</p>' if it.get("for") else "")
            + f'<p class="period">期間：{html.escape(it.get("period") or "終了日未定")}</p>'
            + f'<p class="mnp-rank-links">{"".join(links)}</p>'
            + (cta_box(aff) if aff else "") + "</section>")
    mnp_toc = "".join(f'<a href="#rank{i}">{i}位 {html.escape(it["carrier"])}</a>'
                      for i, it in enumerate(MNP_TOP5["items"][:5], 1))
    mnp_main = (f'<article class="article mnp-page"><h1 class="article-title">{mnp_title}</h1>'
                f'<p class="article-meta"><time datetime="{upd}">{upd.replace("-", "/")} 更新</time></p>'
                f'{PR_NOTE.format("本記事") if A8_LINKMGR_ID else ""}'
                f'<p>{html.escape(mnp_desc)}</p>'
                '<div class="note">選び方：①代表的なプランを1年間使ったときの実質負担（月額料金から割引・還元を引いた金額、通話料・事務手数料は除く）が安い順。'
                '②「過去にその会社を使った人」「同じ特典を受けたことがある人」が対象外になるキャンペーンは、誰でも使えるとは限らないので載せていません。<br>'
                '条件は変わることがあるので、申し込む前に必ず各社の公式サイトで確認してください。</div>'
                f'<nav class="matome-toc">{mnp_toc}</nav>'
                f'<div class="article-body">{"".join(ranks)}</div>'
                f'<p class="related-more related-matome"><a href="{MATOME_PATH}">ほかの開催中キャンペーンもまとめて見る →</a></p>'
                '</article>')
    mnp_ld = {"@context": "https://schema.org", "@type": "ItemList", "name": mnp_title,
              "itemListElement": [{"@type": "ListItem", "position": i + 1,
                                   "name": f'{it["carrier"]} {it["benefit"]}'}
                                  for i, it in enumerate(MNP_TOP5["items"][:5])]}
    p = page(f"{mnp_title} | {SITE_NAME}", mnp_main, mnp_desc, sidebar(""), path=MNP_PATH,
             head=json_ld(mnp_ld))
    (OUT / MNP_PATH).write_text(render(p, "", nav("", "mnp")), encoding="utf-8")

    # RSS フィード（新しい20件）
    def rfc822(a):
        return datetime.fromisoformat(iso_time(a)).strftime("%a, %d %b %Y %H:%M:%S +0900")
    feed_items = "".join(
        f"<item><title>{html.escape(a['title'])}</title><link>{page_url("articles/" + a["slug"])}</link>"
        f"<guid isPermaLink=\"true\">{page_url("articles/" + a["slug"])}</guid><pubDate>{rfc822(a)}</pubDate>"
        f"<category>{html.escape(a['carrier'])}</category><description>{html.escape(a['lead'])}</description>"
        f"<enclosure url=\"{ogp_image(a['slug'])}\" type=\"image/png\" length=\"0\"/></item>"
        for a in articles[:20])
    (OUT / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{SITE_NAME}</title><link>{SITE_URL}</link><description>{html.escape(SITE_DESC)}</description>"
        f'<language>ja</language><atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>'
        + (f"<lastBuildDate>{rfc822(articles[0])}</lastBuildDate>" if articles else "")
        + f"{feed_items}</channel></rss>\n", encoding="utf-8")

    missing = page(f"ページが見つかりません | {SITE_NAME}",
                   '<h1 class="list-heading">ページが見つかりません</h1>'
                   '<p>キャンペーンが終了して記事を整理した可能性があります。</p>'
                   '<p><a href="/index.html">トップページへ戻る</a></p>', sidebar=sidebar("/"))
    (OUT / "404.html").write_text(render(missing, "/", nav("/")), encoding="utf-8")

    # 検索エンジン向けのサイトマップと robots.txt
    urls = ["", MNP_PATH, MATOME_PATH] + [f"articles/{a['slug']}.html" for a in articles]
    urls += [f"carrier/{slug_of[c]}.html" for c in carriers]
    urls += [f"category/{slug}.html" for slug, _, tags in CATEGORIES if in_category(tags)]
    urls += [f"{path.stem}.html" for path in sorted(PAGES.glob("*.md"))]
    latest = {f"articles/{a['slug']}.html": a.get("updated") or a["date"] for a in articles}
    latest[MATOME_PATH] = now.isoformat()
    latest[MNP_PATH] = MNP_TOP5["updated"]
    entries = "".join(
        f"<url><loc>{page_url(u)}</loc><lastmod>{latest.get(u, articles[0]['date'] if articles else today().isoformat())}</lastmod></url>"
        for u in urls)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>\n', encoding="utf-8")
    if ADSENSE_CLIENT:
        pub = ADSENSE_CLIENT.removeprefix("ca-")
        (OUT / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")

    print(f"{len(articles)} 本の記事を docs/ に出力しました")


if __name__ == "__main__":
    main()
