#!/usr/bin/env python3
"""content/*.md から docs/ に静的サイトを生成する（外部ライブラリ不要）。"""
import html
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
OUT = ROOT / "docs"
SITE_NAME = "SIMトク速報"
SITE_DESC = "携帯各社の期間限定キャンペーンを毎日チェックしてわかりやすく紹介"

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
}
JST = timezone(timedelta(hours=9))


def today():
    """ビルド環境のタイムゾーンに関係なく日本時間の日付を返す。"""
    return datetime.now(JST).date()


DEFAULT_COLOR = ("#e9e3ff", "#5b4bb7")
CARRIER_SLUGS = {
    "ドコモ": "docomo", "ahamo": "ahamo", "au": "au", "UQ mobile": "uqmobile", "povo": "povo",
    "ソフトバンク": "softbank", "ワイモバイル": "ymobile", "LINEMO": "linemo", "楽天モバイル": "rakuten",
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
    bg, fg = CARRIER_COLORS.get(article["carrier"], DEFAULT_COLOR)
    label = html.escape(article.get("thumb", article["carrier"]))
    carrier = html.escape(article["carrier"])
    return (f'<div class="thumb" style="--tbg:{bg};--tfg:{fg}">'
            f'<span class="thumb-carrier">{carrier}</span>'
            f'<span class="thumb-label">{label}</span></div>')


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


def page(title, main, description=SITE_DESC, sidebar=""):
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="stylesheet" href="{{root}}static/style.css">
</head>
<body>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="{{root}}index.html"><span class="logo-mark">SIM</span>トク速報</a>
    <p class="tagline">{html.escape(SITE_DESC)}</p>
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
</body>
</html>"""


def render(template, root, nav):
    return template.replace("{root}", root).replace("{nav}", nav)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "articles").mkdir(parents=True)
    (OUT / "carrier").mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")

    articles = []
    for path in CONTENT.glob("*.md"):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        meta["slug"] = path.stem
        meta["body"] = markdown_to_html(body)
        articles.append(meta)
    articles.sort(key=lambda a: (a["date"], a.get("time", "")), reverse=True)

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

    def sidebar(root):
        soon = [a for a in articles if a.get("end") and 0 <= (date.fromisoformat(a["end"]) - today()).days <= 14]
        soon.sort(key=lambda a: a["end"])
        items = "".join(
            f'<li><a href="{root}articles/{a["slug"]}.html">{html.escape(a["title"])}</a>'
            f'<span class="side-date">{a["end"][5:].replace("-", "/")}まで</span></li>' for a in soon
        ) or "<li>2週間以内に終わるキャンペーンはありません</li>"
        cs = "".join(f'<li><a href="{root}carrier/{slug_of[c]}.html">{html.escape(c)}</a></li>' for c in carriers)
        return (f'<section class="side-box side-pink"><h2>まもなく終了</h2><ul>{items}</ul></section>'
                f'<section class="side-box side-mint"><h2>キャリア別</h2><ul class="side-carriers">{cs}</ul></section>')

    index = page(SITE_NAME, list_main(articles, "新着キャンペーン", ""), sidebar=sidebar(""))
    (OUT / "index.html").write_text(render(index, "", nav("")), encoding="utf-8")

    for c in carriers:
        items = [a for a in articles if a["carrier"] == c]
        p = page(f"{c}のキャンペーン | {SITE_NAME}", list_main(items, f"{html.escape(c)}のキャンペーン", "../"),
                 sidebar=sidebar("../"))
        (OUT / "carrier" / f"{slug_of[c]}.html").write_text(render(p, "../", nav("../")), encoding="utf-8")

    for a in articles:
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in a["tags"])
        period = f'<p class="period">キャンペーン期間：{html.escape(a["period"])}</p>' if a.get("period") else ""
        source = (f'<p class="source">公式情報：<a href="{html.escape(a["source"])}" target="_blank" rel="noopener">'
                  f'{html.escape(a["source"])}</a></p>') if a.get("source") else ""
        main_html = f"""<article class="article">
  <p class="article-meta"><time>{a['date'].replace('-', '/')} {a.get('time', '')}</time>{deadline_badge(a)}</p>
  <h1 class="article-title">{html.escape(a['title'])}</h1>
  <p class="card-tags">{tags}</p>
  {thumb(a).replace('class="thumb"', 'class="thumb thumb-large"')}
  {period}
  <div class="article-body">{a['body']}</div>
  {source}
  <p class="back"><a href="../index.html">← 記事一覧へ戻る</a></p>
</article>"""
        p = page(f"{a['title']} | {SITE_NAME}", main_html, a["lead"], sidebar("../"))
        (OUT / "articles" / f"{a['slug']}.html").write_text(render(p, "../", nav("../")), encoding="utf-8")

    missing = page(f"ページが見つかりません | {SITE_NAME}",
                   '<h1 class="list-heading">ページが見つかりません</h1>'
                   '<p>キャンペーンが終了して記事を整理した可能性があります。</p>'
                   '<p><a href="/index.html">トップページへ戻る</a></p>', sidebar=sidebar("/"))
    (OUT / "404.html").write_text(render(missing, "/", nav("/")), encoding="utf-8")

    print(f"{len(articles)} 本の記事を docs/ に出力しました")


if __name__ == "__main__":
    main()
