"""IndexNow で Bing などの検索エンジンに、新しく公開・更新したページを知らせる。

使い方:
  python3 scripts/indexnow.py content/2026-11-21-xxx.md ...   # 記事（＋トップ・まとめ・MNP）を通知
  python3 scripts/indexnow.py --all                           # サイトマップの全URLを通知（初回用）

ページが公開されるまで（最大10分）待ってから送る。キーは build.py の INDEXNOW_KEY。
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import INDEXNOW_KEY, SITE_HOST, SITE_URL  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"
UA = {"User-Agent": "simsoku-indexnow/1.0"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read().decode("utf-8", "replace")


def is_live(url):
    try:
        return fetch(url)[0] == 200
    except Exception:
        return False


def wait_live(urls, limit=600):
    """キーのファイルと各ページが公開されるのを待つ。公開されたURLだけを返す。"""
    key_url = f"{SITE_URL}{INDEXNOW_KEY}.txt"
    deadline = time.time() + limit
    pending = [key_url] + list(urls)
    while pending and time.time() < deadline:
        pending = [u for u in pending if not is_live(u)]
        if pending:
            time.sleep(30)
    if key_url in pending:
        sys.exit(f"キーのファイルが公開されていません: {key_url}")
    return [u for u in urls if u not in pending]


def main(args):
    if not INDEXNOW_KEY:
        print("INDEXNOW_KEY が空なので何もしません")
        return
    if args == ["--all"]:
        _, xml = fetch(f"{SITE_URL}sitemap.xml")
        urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    else:
        urls = [SITE_URL, f"{SITE_URL}campaigns", f"{SITE_URL}mnp"]
        for a in args:
            p = Path(a)
            if p.suffix == ".md" and p.parent.name == "content" and (ROOT / p).exists():
                urls.append(f"{SITE_URL}articles/{p.stem}")
            elif p.suffix == ".md" and p.parent.name == "guides" and (ROOT / p).exists():
                urls.append(f"{SITE_URL}guide/{p.stem}")
        urls = list(dict.fromkeys(urls))
    urls = wait_live(urls)
    if not urls:
        print("通知するURLがありません")
        return
    body = json.dumps({
        "host": SITE_HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}{INDEXNOW_KEY}.txt",
        "urlList": urls[:10000],
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={**UA, "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: {r.status}（{len(urls)}件）")
    except urllib.error.HTTPError as e:
        sys.exit(f"IndexNow: {e.code} {e.read().decode('utf-8', 'replace')[:300]}")
    for u in urls:
        print(" ", u)


if __name__ == "__main__":
    main(sys.argv[1:])
