#!/usr/bin/env python3
"""キャリア公式ページから乗り換え（MNP）の端末価格を拾い、前回との差分を Markdown で出す（外部ライブラリ不要）。

GitHub Actions（.github/workflows/mnp-watch.yml）から毎日呼ばれ、変化があれば Issue になる。
取得先は watch/mnp_sources.json。robots.txt で禁止されているページは取りに行かない。
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
SOURCES = ROOT / "mnp_sources.json"
USER_AGENT = "SIMtokuSokuhouBot/1.0 (+https://github.com/lindwurm310/sim_sokuhou)"
WAIT_SECONDS = 5  # 同じサイトへ続けてアクセスするときの間隔
JST = timezone(timedelta(hours=9))

# 価格の行とみなす条件：金額が入っていて、乗り換えや割引の言葉がある
YEN = re.compile(r"\d[\d,]*\s*円")
KEYWORDS = re.compile(r"乗り換え|乗りかえ|のりかえ|MNP|他社から|割引|値引|一括|実質|/月|／月|月額|総額")
MAX_LINE = 200


class TextExtractor(HTMLParser):
    """script / style を除いた本文テキストを、ブロック要素ごとの行に分けて取り出す。"""

    SKIP = {"script", "style", "noscript", "template", "svg"}
    BLOCK = {"p", "div", "li", "tr", "td", "th", "dt", "dd", "br", "h1", "h2", "h3", "h4", "h5", "h6",
             "section", "article", "table", "ul", "ol", "dl", "caption", "figcaption"}

    def __init__(self):
        super().__init__()
        self.lines = []
        self.buf = []
        self.skip_depth = 0

    def flush(self):
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if text:
            self.lines.append(text)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in self.BLOCK:
            self.flush()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in self.BLOCK:
            self.flush()

    def handle_data(self, data):
        if not self.skip_depth:
            self.buf.append(data)

    def close(self):
        super().close()
        self.flush()


def price_lines(html_text):
    parser = TextExtractor()
    parser.feed(html_text)
    parser.close()
    seen, out = set(), []
    for line in parser.lines:
        if len(line) > MAX_LINE or not YEN.search(line) or not KEYWORDS.search(line):
            continue
        if line not in seen:
            seen.add(line)
            out.append(line)
    return out


_robots = {}


def allowed(url):
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as res:
                rp.parse(res.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            # robots.txt が無い（4xx）なら全許可、サーバーエラーなら取りに行かない
            rp.parse([] if 400 <= e.code < 500 else ["User-agent: *", "Disallow: /"])
        _robots[base] = rp
        time.sleep(WAIT_SECONDS)
    return _robots[base].can_fetch(USER_AGENT, url)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=30) as res:
        charset = res.headers.get_content_charset() or "utf-8"
        return res.read().decode(charset, "replace")


def check(source):
    """1つの取得先を調べて {"lines": [...]} か {"error": "..."} を返す。"""
    url = source["url"]
    try:
        if not allowed(url):
            return {"error": "robots.txt で取得が禁止されています"}
        lines = price_lines(fetch(url))
    except Exception as e:  # ネットワークやHTTPのエラーはまとめて報告する
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        time.sleep(WAIT_SECONDS)
    if not lines:
        return {"error": "価格の行が見つかりません（ページの作りが変わったかもしれません）"}
    return {"lines": lines}


def build_report(sources, old, new, today):
    """変化があった取得先だけを Markdown にまとめる。何もなければ空文字。"""
    parts = []
    for s in sources:
        sid, prev, cur = s["id"], old.get(s["id"], {}), new[s["id"]]
        head = f"## {s['carrier']}：{s['name']}\n\n{s['url']}\n"
        if "error" in cur:
            # 失敗は初めて失敗した日だけ知らせる（毎日同じ Issue が立たないように）
            if cur.get("failing_since") == today:
                parts.append(f"{head}\n:warning: 取得に失敗しました：{cur['error']}\n")
            continue
        if "lines" not in prev:
            body = "\n".join(f"- {line}" for line in cur["lines"])
            parts.append(f"{head}\n初めて取得しました。今の価格の行：\n\n{body}\n")
            continue
        added = [l for l in cur["lines"] if l not in prev["lines"]]
        removed = [l for l in prev["lines"] if l not in cur["lines"]]
        if added or removed:
            body = "\n".join([f"- :new: {l}" for l in added] + [f"- ~~{l}~~" for l in removed])
            parts.append(f"{head}\n{body}\n")
    if not parts:
        return ""
    intro = ("キャリア公式ページの乗り換え価格に変化がありました。:new: は増えた行、取り消し線は消えた行です。\n"
             "記事にするときは、リンク先で条件と期間を確認してください。\n")
    return intro + "\n" + "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", type=Path, default=ROOT / "mnp_snapshot.json", help="前回の取得結果")
    ap.add_argument("--report", type=Path, help="変化があれば Markdown をここに書く")
    ap.add_argument("--dry-run", action="store_true", help="取得結果を表示するだけで snapshot を更新しない")
    args = ap.parse_args()

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    old = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot.exists() else {}
    today = datetime.now(JST).strftime("%Y-%m-%d")

    new = {}
    for s in sources:
        result = check(s)
        prev = old.get(s["id"], {})
        if "error" in result:
            print(f"[NG] {s['id']}: {result['error']}", file=sys.stderr)
            # 失敗した日は前回の行を残して、次に取れたときに正しく差分を出す
            result = {**{k: v for k, v in prev.items() if k == "lines"}, **result,
                      "failing_since": prev.get("failing_since") or today}
        else:
            print(f"[OK] {s['id']}: {len(result['lines'])} 行")
            if args.dry_run:
                for line in result["lines"]:
                    print(f"     {line}")
        new[s["id"]] = result

    report = build_report(sources, old, new, today)
    if args.report and report:
        args.report.write_text(report, encoding="utf-8")
    print("変化あり" if report else "変化なし")
    if not args.dry_run:
        args.snapshot.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
