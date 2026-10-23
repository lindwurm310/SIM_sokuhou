#!/usr/bin/env python3
"""新しく追加された記事を X（旧Twitter）に投稿する（外部ライブラリ不要）。

使い方: python3 scripts/post_to_x.py content/2026-10-23-xxx.md [...]

環境変数
  X_POST_ENABLED      "true" のときだけ実際に投稿する。それ以外は投稿文を表示するだけ（お試し）。
  X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET
                      X Developer Console で発行した OAuth 1.0a のキー4つ。
  X_INCLUDE_URL       "false" にすると記事URLを入れずに投稿する（X API はURL入り投稿が割高なため）。
  X_WAIT_FOR_PAGE     "false" にすると記事ページの公開待ちをしない。
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import SITE_URL, parse_front_matter  # noqa: E402

API_URL = "https://api.x.com/2/tweets"
MAX_WEIGHT = 280  # X の文字数上限（全角は2、半角は1として数える）
URL_WEIGHT = 23  # URL は長さに関係なく23として数えられる
HASHTAGS = ["格安SIM", "キャンペーン"]


def env_flag(name, default):
    return os.environ.get(name, default).strip().lower() == "true"


def char_weight(ch):
    """X の文字数カウント（twitter-text）の規則：半角英数や一部の記号は1、それ以外は2。"""
    cp = ord(ch)
    if cp <= 0x10FF or 0x2000 <= cp <= 0x200D or 0x2010 <= cp <= 0x201F or 0x2032 <= cp <= 0x2037:
        return 1
    return 2


def weight(text):
    total, pos = 0, 0
    for m in re.finditer(r"https?://\S+", text):
        total += sum(char_weight(c) for c in text[pos:m.start()]) + URL_WEIGHT
        pos = m.end()
    return total + sum(char_weight(c) for c in text[pos:])


def hashtag(name):
    """ハッシュタグに使えない空白や記号を取り除く（例：U-NEXT MOBILE → UNEXTMOBILE）。"""
    return "#" + re.sub(r"[^\w]", "", name)


def compose(meta, slug, include_url=True):
    url = f"{SITE_URL}articles/{slug}.html"
    tags = " ".join(hashtag(t) for t in [meta.get("carrier", "")] + HASHTAGS if t)
    title = meta["title"]
    carrier = meta.get("carrier", "")
    head = f"【{carrier}】" if carrier and not title.startswith(carrier) else ""
    point = f"\n\n▶ {meta['thumb']}" if meta.get("thumb") else ""
    tail = (f"\n\n{url}" if include_url else "") + f"\n{tags}"

    def build(t):
        return f"{head}{t}{point}{tail}"

    # 長すぎるときは見どころ → タイトル末尾の順に削る
    if weight(build(title)) > MAX_WEIGHT:
        point = ""
    while weight(build(title)) > MAX_WEIGHT and len(title) > 1:
        title = title[:-2] + "…"
    return build(title), url


def oauth_header(method, url, key, key_secret, token, token_secret):
    """OAuth 1.0a（HMAC-SHA1）の Authorization ヘッダーを作る。JSON本文は署名に含めない。"""
    params = {
        "oauth_consumer_key": key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    q = lambda s: urllib.parse.quote(s, safe="~")  # noqa: E731
    param_str = "&".join(f"{q(k)}={q(v)}" for k, v in sorted(params.items()))
    base = "&".join([method, q(url), q(param_str)])
    signing_key = f"{q(key_secret)}&{q(token_secret)}"
    sig = hmac.new(signing_key.encode(), base.encode(), hashlib.sha1).digest()
    params["oauth_signature"] = base64.b64encode(sig).decode()
    return "OAuth " + ", ".join(f'{q(k)}="{q(v)}"' for k, v in sorted(params.items()))


def post(text):
    creds = [os.environ.get(n, "") for n in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")]
    if not all(creds):
        sys.exit("X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET が設定されていません")
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"text": text}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": oauth_header("POST", API_URL, *creds)},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.load(res)["data"]["id"]
    except urllib.error.HTTPError as e:
        sys.exit(f"X への投稿に失敗しました（HTTP {e.code}）: {e.read().decode(errors='replace')}")


def wait_until_live(url, timeout=600):
    """Cloudflare の再公開が終わって記事ページが開けるようになるまで待つ。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15) as res:
                if res.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(20)
    return False


def main(paths):
    enabled = env_flag("X_POST_ENABLED", "false")
    include_url = env_flag("X_INCLUDE_URL", "true")
    wait = env_flag("X_WAIT_FOR_PAGE", "true")
    if not enabled:
        print("※ お試しモード：投稿はしません（リポジトリ変数 X_POST_ENABLED を true にすると投稿します）\n")
    for i, p in enumerate(paths):
        path = Path(p)
        if path.suffix != ".md" or not path.exists():
            continue
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        text, url = compose(meta, path.stem, include_url)
        print(f"--- {path.name}（{weight(text)}/{MAX_WEIGHT}）\n{text}\n")
        if not enabled:
            continue
        if include_url and wait and not wait_until_live(url):
            sys.exit(f"記事ページが公開されないため投稿を中止しました: {url}")
        if i:
            time.sleep(30)  # 連投にならないよう少し間をあける
        print(f"投稿しました: https://x.com/i/web/status/{post(text)}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
