// 静的ページは assets がそのまま返し、/api/* だけこの Worker が受け持つ（wrangler.jsonc の run_worker_first）。
// 記事ごとの累計閲覧数は SQLite の Durable Object（無料プランで使える）1つにまとめて持つ。
import { DurableObject } from "cloudflare:workers";

const SLUG = /^[0-9a-z-]{1,120}$/;
const RANKING_TTL = 300; // ランキングは5分キャッシュして Durable Object への問い合わせを減らす

export class Counter extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS views (slug TEXT PRIMARY KEY, count INTEGER NOT NULL)");
  }

  hit(slug) {
    this.ctx.storage.sql.exec(
      "INSERT INTO views (slug, count) VALUES (?, 1) ON CONFLICT(slug) DO UPDATE SET count = count + 1", slug);
  }

  top(limit) {
    return this.ctx.storage.sql.exec("SELECT slug, count FROM views ORDER BY count DESC LIMIT ?", limit).toArray();
  }
}

function json(data, headers = {}) {
  return new Response(JSON.stringify(data), {
    headers: { "content-type": "application/json; charset=utf-8", ...headers },
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const counter = env.COUNTER.get(env.COUNTER.idFromName("views"));

    if (url.pathname === "/api/hit" && request.method === "POST") {
      const slug = url.searchParams.get("slug") || "";
      if (!SLUG.test(slug)) return new Response(null, { status: 400 });
      // 存在しない記事を数えないよう、記事ページがあるか確かめてから数える
      const page = await env.ASSETS.fetch(new URL(`/articles/${slug}.html`, url), { method: "HEAD" });
      if (!page.ok) return new Response(null, { status: 404 });
      await counter.hit(slug);
      return new Response(null, { status: 204 });
    }

    if (url.pathname === "/api/ranking" && request.method === "GET") {
      const cache = caches.default;
      const key = new Request(new URL("/api/ranking", url));
      const cached = await cache.match(key);
      if (cached) return cached;
      const res = json({ ranking: await counter.top(30) }, { "cache-control": `public, max-age=${RANKING_TTL}` });
      ctx.waitUntil(cache.put(key, res.clone()));
      return res;
    }

    return new Response("Not Found", { status: 404 });
  },
};
