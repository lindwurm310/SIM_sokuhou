#!/usr/bin/env python3
"""新しく追加された記事を X（旧Twitter）や Bluesky に投稿する（外部ライブラリ不要）。

使い方: python3 scripts/post_to_x.py content/2026-10-23-xxx.md [...]

何も設定しなければ投稿文を表示するだけ。設定に応じて次のことをする。
  X_INTENT_OUT        ファイルのパスを入れると、「Xで投稿する」リンク（X公式の共有リンク、無料）を
                      Markdown で書き出す。GitHub Actions はこれを Issue にしてスマホに通知する。
  X_POST_ENABLED      "true" のとき X API で自動投稿する（有料。キー4つが必要）。
  X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET
                      X Developer Console で発行した OAuth 1.0a のキー4つ。
  BLUESKY_POST_ENABLED "true" のとき Bluesky に自動投稿する（無料）。
  BLUESKY_HANDLE / BLUESKY_APP_PASSWORD
                      Bluesky のハンドル（例：simtoku.bsky.social）とアプリパスワード。
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
BLUESKY_MAX = 300  # Bluesky の文字数上限
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


def compose(meta, slug, include_url=True, measure=weight, limit=MAX_WEIGHT):
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
    if measure(build(title)) > limit:
        point = ""
    while measure(build(title)) > limit and len(title) > 1:
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


def intent_link(text):
    """X 公式の共有リンク。開くと投稿文が入った状態で X が開き、自分で投稿ボタンを押す（無料）。"""
    return "https://x.com/intent/post?text=" + urllib.parse.quote(text, safe="")


def bluesky_facets(text):
    """Bluesky で URL とハッシュタグをリンクにするための位置情報（UTF-8 のバイト位置で指定する）。"""
    facets = []
    for m in re.finditer(r"https?://\S+|#\w+", text):
        start = len(text[:m.start()].encode())
        end = start + len(m.group().encode())
        if m.group().startswith("#"):
            feature = {"$type": "app.bsky.richtext.facet#tag", "tag": m.group()[1:]}
        else:
            feature = {"$type": "app.bsky.richtext.facet#link", "uri": m.group()}
        facets.append({"index": {"byteStart": start, "byteEnd": end}, "features": [feature]})
    return facets


def post_bluesky(text, meta, url):
    handle, password = os.environ.get("BLUESKY_HANDLE", ""), os.environ.get("BLUESKY_APP_PASSWORD", "")
    if not (handle and password):
        sys.exit("BLUESKY_HANDLE / BLUESKY_APP_PASSWORD が設定されていません")

    def call(method, body, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(f"https://bsky.social/xrpc/{method}", data=json.dumps(body).encode(),
                                     method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.load(res)
        except urllib.error.HTTPError as e:
            sys.exit(f"Bluesky への投稿に失敗しました（HTTP {e.code}）: {e.read().decode(errors='replace')}")

    session = call("com.atproto.server.createSession", {"identifier": handle, "password": password})
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "facets": bluesky_facets(text),
        "langs": ["ja"],
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # 記事のリンクカード（画像なし）
        "embed": {"$type": "app.bsky.embed.external",
                  "external": {"uri": url, "title": meta["title"], "description": meta.get("lead", "")}},
    }
    res = call("com.atproto.repo.createRecord",
               {"repo": session["did"], "collection": "app.bsky.feed.post", "record": record}, session["accessJwt"])
    return "https://bsky.app/profile/{}/post/{}".format(handle, res["uri"].rsplit("/", 1)[-1])


def main(paths):
    x_api = env_flag("X_POST_ENABLED", "false")
    bluesky = env_flag("BLUESKY_POST_ENABLED", "false")
    include_url = env_flag("X_INCLUDE_URL", "true")
    wait = env_flag("X_WAIT_FOR_PAGE", "true")
    intent_out = os.environ.get("X_INTENT_OUT", "")
    links = []
    for i, p in enumerate(paths):
        path = Path(p)
        if path.suffix != ".md" or not path.exists():
            continue
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        text, url = compose(meta, path.stem, include_url)
        print(f"--- {path.name}（{weight(text)}/{MAX_WEIGHT}）\n{text}\n")
        links.append(f"### {meta['title']}\n\n**[▶ Xで投稿する]({intent_link(text)})**\n\n```\n{text}\n```\n")
        if not (x_api or bluesky or intent_out):
            continue
        if include_url and wait and not wait_until_live(url):
            sys.exit(f"記事ページが公開されないため投稿を中止しました: {url}")
        if i:
            time.sleep(30)  # 連投にならないよう少し間をあける
        if x_api:
            print(f"X に投稿しました: https://x.com/i/web/status/{post(text)}\n")
        if bluesky:
            print(f"Bluesky に投稿しました: {post_bluesky(compose(meta, path.stem, True, len, BLUESKY_MAX)[0], meta, url)}\n")
    if intent_out and links:
        Path(intent_out).write_text(
            "新しい記事が公開されました。リンクを開くと投稿文が入った状態で X が開くので、内容を確かめて投稿してください。"
            "投稿が済んだらこの Issue を閉じてください。\n\n" + "\n".join(links), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
