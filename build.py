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
OUT = ROOT / "docs"
SITE_NAME = "SIMトク速報"
SITE_URL = "https://sim-sokuhou.lindwurm310.workers.dev/"
SITE_DESC = "携帯各社の期間限定キャンペーンを毎日チェックしてわかりやすく紹介"
# サイドバーに出す X（旧Twitter）アカウントのURL。空のままならリンク欄は出さない。
X_URL = ""

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
}
JST = timezone(timedelta(hours=9))

# サイドバーのカテゴリ。記事の tags のどれかが含まれていればそのカテゴリに入る。
CATEGORIES = [
    ("mnp", "MNP（乗り換え）", {"MNP"}),
    ("device", "端末割引・一括1円", {"端末割引", "一括1円", "iPhone", "Android", "返却プログラム"}),
    ("fee", "事務手数料無料", {"事務手数料無料"}),
    ("point", "ポイント・残高還元", {"ポイント還元", "残高還元", "キャッシュバック"}),
    ("simonly", "SIMのみ契約", {"SIMのみ"}),
]


def today():
    """ビルド環境のタイムゾーンに関係なく日本時間の日付を返す。"""
    return datetime.now(JST).date()


DEFAULT_COLOR = ("#e9e3ff", "#5b4bb7")
CARRIER_SLUGS = {
    "ドコモ": "docomo", "ahamo": "ahamo", "au": "au", "UQ mobile": "uqmobile", "povo": "povo",
    "ソフトバンク": "softbank", "ワイモバイル": "ymobile", "LINEMO": "linemo", "楽天モバイル": "rakuten",
    "U-NEXT MOBILE": "unext",
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


def thumb(article):
    """公式サイトの画像があれば使い、読み込めないときはキャリア色のカードを見せる。"""
    bg, fg = CARRIER_COLORS.get(article["carrier"], DEFAULT_COLOR)
    label = html.escape(article.get("thumb", article["carrier"]))
    carrier = html.escape(article["carrier"])
    img = ""
    if article.get("image"):
        img = (f'<img class="thumb-img" src="{html.escape(article["image"])}" alt="" loading="lazy" '
               f'referrerpolicy="no-referrer" onerror="this.remove()">')
    return (f'<div class="thumb" style="--tbg:{bg};--tfg:{fg}">'
            f'<span class="thumb-carrier">{carrier}</span>'
            f'<span class="thumb-label">{label}</span>{img}</div>')


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


def page(title, main, description=SITE_DESC, sidebar="", path="", image=""):
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{SITE_URL}{path}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{SITE_URL}{path}">
<meta property="og:type" content="{'article' if path.startswith('articles/') else 'website'}">
{f'<meta property="og:image" content="{html.escape(image)}">' if image else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{{root}}static/style.css">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t;}}catch(e){{}}</script>
</head>
<body data-root="{{root}}" data-slug="{path[9:-5] if path.startswith('articles/') else ''}">
<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="{{root}}index.html"><span class="logo-mark">SIM</span>トク速報</a>
    <p class="tagline">{html.escape(SITE_DESC)}</p>
    <button class="theme-toggle" type="button" aria-label="ダークモード切り替え" onclick="toggleTheme()">
      <span class="icon-dark">🌙 ダーク</span><span class="icon-light">☀️ ライト</span>
    </button>
  </div>
  <nav class="carrier-nav"><div class="wrap">{{nav}}</div></nav>
</header>
<div class="wrap layout">
  <main>{main}</main>
  <aside class="sidebar">{sidebar}</aside>
</div>
<footer class="site-footer"><div class="wrap">
  <p>掲載内容は記事公開時点の情報です。最新の条件は必ず各社公式サイトでご確認ください。</p>
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
</body>
</html>"""


def render(template, root, nav):
    return template.replace("{root}", root).replace("{nav}", nav)


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
         "bg": CARRIER_COLORS.get(a["carrier"], DEFAULT_COLOR)[0], "fg": CARRIER_COLORS.get(a["carrier"], DEFAULT_COLOR)[1]}
        for a in articles], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    carriers = sorted({a["carrier"] for a in articles},
                      key=lambda c: list(CARRIER_COLORS).index(c) if c in CARRIER_COLORS else 99)
    slug_of = {c: CARRIER_SLUGS.get(c, f"carrier{i}") for i, c in enumerate(carriers)}

    def nav(root):
        links = [f'<a href="{root}index.html">すべて</a>']
        links += [f'<a href="{root}carrier/{slug_of[c]}.html">{html.escape(c)}</a>' for c in carriers]
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

    def list_main(items, heading, root):
        groups, out = {}, [f'<h1 class="list-heading">{heading}</h1>']
        for a in items:
            groups.setdefault(a["date"], []).append(a)
        for d, group in groups.items():
            y, m, dd = d.split("-")
            out.append(f'<h2 class="date-heading">{int(y)}年{int(m)}月{int(dd)}日の記事</h2>')
            out += [card(a, root) for a in group]
        return "\n".join(out)

    def in_category(tags):
        return [a for a in articles if tags & set(a["tags"])]

    handle = X_URL.rstrip("/").rsplit("/", 1)[-1]
    x_box = (f'<section class="side-box side-x"><h2>公式X</h2><p>新着キャンペーンをXでもお知らせしています。</p>'
             f'<a class="x-follow" href="{html.escape(X_URL)}" target="_blank" rel="noopener">'
             f'<span class="x-logo" aria-hidden="true">𝕏</span>@{html.escape(handle)} をフォロー</a></section>'
             if X_URL else "")
    # 中身は static/sidebar.js が埋める
    extra_boxes = ('<section class="side-box side-peach" id="side-ranking"><h2>累計アクセスランキング</h2>'
                   '<ol class="side-ranking"><li class="side-empty">読み込み中…</li></ol></section>'
                   '<section class="side-box side-sky" id="side-recommend"><h2>あなたへのおすすめ</h2>'
                   '<p class="side-note"></p><ul class="side-picks"><li class="side-empty">読み込み中…</li></ul></section>'
                   + x_box)

    def sidebar(root):
        soon = [a for a in articles if a.get("end") and 0 <= (date.fromisoformat(a["end"]) - today()).days <= 14]
        soon.sort(key=lambda a: a["end"])
        items = "".join(
            f'<li><a href="{root}articles/{a["slug"]}.html">{html.escape(a["title"])}</a>'
            f'<span class="side-date">{a["end"][5:].replace("-", "/")}まで</span></li>' for a in soon
        ) or "<li>2週間以内に終わるキャンペーンはありません</li>"
        cs = "".join(f'<li><a href="{root}carrier/{slug_of[c]}.html">{html.escape(c)}</a></li>' for c in carriers)
        cats = "".join(
            f'<li><a href="{root}category/{slug}.html">{html.escape(name)}'
            f'<span class="count">{len(in_category(tags))}</span></a></li>'
            for slug, name, tags in CATEGORIES if in_category(tags))
        return (f'<section class="side-box side-lavender"><h2>カテゴリ</h2><ul class="side-categories">{cats}</ul></section>'
                f'<section class="side-box side-pink"><h2>まもなく終了</h2><ul>{items}</ul></section>' + extra_boxes +
                f'<section class="side-box side-mint"><h2>キャリア別</h2><ul class="side-carriers">{cs}</ul></section>')

    index = page(SITE_NAME, list_main(articles, "新着キャンペーン", ""), sidebar=sidebar(""), path="")
    (OUT / "index.html").write_text(render(index, "", nav("")), encoding="utf-8")

    for c in carriers:
        items = [a for a in articles if a["carrier"] == c]
        p = page(f"{c}のキャンペーン | {SITE_NAME}", list_main(items, f"{html.escape(c)}のキャンペーン", "../"),
                 sidebar=sidebar("../"), path=f"carrier/{slug_of[c]}.html")
        (OUT / "carrier" / f"{slug_of[c]}.html").write_text(render(p, "../", nav("../")), encoding="utf-8")

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
        main_html = f"""<article class="article">
  <p class="article-meta"><time>{a['date'].replace('-', '/')} {a.get('time', '')}</time>{deadline_badge(a)}</p>
  <h1 class="article-title">{html.escape(a['title'])}</h1>
  <p class="card-tags">{tags}</p>
  {thumb(a).replace('class="thumb"', 'class="thumb thumb-large"')}
  {credit}
  {period}
  <div class="article-body">{a['body']}</div>
  {source}
  <p class="back"><a href="../index.html">← 記事一覧へ戻る</a></p>
</article>"""
        p = page(f"{a['title']} | {SITE_NAME}", main_html, a["lead"], sidebar("../"),
                 path=f"articles/{a['slug']}.html", image=a.get("image", ""))
        (OUT / "articles" / f"{a['slug']}.html").write_text(render(p, "../", nav("../")), encoding="utf-8")

    missing = page(f"ページが見つかりません | {SITE_NAME}",
                   '<h1 class="list-heading">ページが見つかりません</h1>'
                   '<p>キャンペーンが終了して記事を整理した可能性があります。</p>'
                   '<p><a href="/index.html">トップページへ戻る</a></p>', sidebar=sidebar("/"))
    (OUT / "404.html").write_text(render(missing, "/", nav("/")), encoding="utf-8")

    # 検索エンジン向けのサイトマップと robots.txt
    urls = [""] + [f"articles/{a['slug']}.html" for a in articles]
    urls += [f"carrier/{slug_of[c]}.html" for c in carriers]
    urls += [f"category/{slug}.html" for slug, _, tags in CATEGORIES if in_category(tags)]
    latest = {f"articles/{a['slug']}.html": a["date"] for a in articles}
    entries = "".join(
        f"<url><loc>{SITE_URL}{u}</loc><lastmod>{latest.get(u, articles[0]['date'] if articles else today().isoformat())}</lastmod></url>"
        for u in urls)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>\n', encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")

    print(f"{len(articles)} 本の記事を docs/ に出力しました")


if __name__ == "__main__":
    main()
