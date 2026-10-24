// サイドバーの「アクセスランキング」と「あなたへのおすすめ」。記事一覧は data/articles.json から読む。
(function () {
  var body = document.body;
  var root = body.dataset.root || "";
  var current = body.dataset.slug || "";
  var today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10); // 日本時間の日付

  function load(key, fallback) {
    try { var v = JSON.parse(localStorage.getItem(key)); return v == null ? fallback : v; } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; });
  }
  function item(a, extra) {
    return '<li><a href="' + root + "articles/" + a.slug + '.html">' +
      '<span class="side-carrier" style="--tbg:' + a.bg + ";--tfg:" + a.fg + '">' + esc(a.carrier) + "</span>" +
      esc(a.title) + "</a>" + (extra || "") + "</li>";
  }

  // 記事ページなら閲覧履歴に残し、同じ記事は1日1回だけアクセス数に数える
  var history = load("history", []);
  if (current) {
    history = [current].concat(history.filter(function (s) { return s !== current; })).slice(0, 30);
    save("history", history);
    var counted = load("counted", {});
    if (counted[current] !== today) {
      for (var k in counted) if (counted[k] !== today) delete counted[k];
      counted[current] = today;
      save("counted", counted);
      fetch("/api/hit?slug=" + encodeURIComponent(current), { method: "POST", keepalive: true }).catch(function () {});
    }
  }

  fetch(root + "data/articles.json").then(function (r) { return r.json(); }).then(function (articles) {
    var bySlug = {};
    articles.forEach(function (a) { bySlug[a.slug] = a; });
    ranking(bySlug);
    recommend(articles, bySlug);
  }).catch(function () {});

  function ranking(bySlug) {
    var box = document.getElementById("side-ranking");
    if (!box) return;
    var list = box.querySelector("ol");
    var cache = load("ranking", null); // 10分は端末に覚えておき、リクエストを減らす
    var p = cache && Date.now() - cache.t < 600000 ? Promise.resolve(cache.data)
      : fetch("/api/ranking").then(function (r) { if (!r.ok) throw r; return r.json(); })
          .then(function (d) { save("ranking", { t: Date.now(), data: d }); return d; });
    p.then(function (d) {
      var rows = d.ranking.filter(function (r) { return bySlug[r.slug]; }).slice(0, 5);
      if (!rows.length) { list.innerHTML = '<li class="side-empty">集計を始めたばかりです</li>'; return; }
      list.innerHTML = rows.map(function (r) {
        return item(bySlug[r.slug], '<span class="side-views">' + r.count.toLocaleString() + " 回閲覧</span>");
      }).join("");
    }).catch(function () { box.hidden = true; });
  }

  function recommend(articles, bySlug) {
    var box = document.getElementById("side-recommend");
    if (!box) return;
    // 最近読んだ記事ほど重く、同じキャリアと共通のタグを手がかりに点数をつける
    var seen = {}, carriers = {}, tags = {};
    history.forEach(function (slug, i) {
      var a = bySlug[slug];
      seen[slug] = true;
      if (!a) return;
      var w = slug === current ? 3 : 1 / (1 + i * 0.3);
      carriers[a.carrier] = (carriers[a.carrier] || 0) + w;
      a.tags.forEach(function (t) { tags[t] = (tags[t] || 0) + w; });
    });
    var open = articles.filter(function (a) { return !seen[a.slug] && (!a.end || a.end >= today); });
    open.forEach(function (a, i) {
      a.score = (carriers[a.carrier] || 0) * 2;
      a.tags.forEach(function (t) { a.score += tags[t] || 0; });
      a.order = i; // articles.json は新しい順
    });
    var personal = open.some(function (a) { return a.score > 0; });
    open.sort(function (a, b) { return b.score - a.score || a.order - b.order; });
    var picks = open.slice(0, 5);
    if (!picks.length) { box.hidden = true; return; }
    box.querySelector("ul").innerHTML = picks.map(function (a) { return item(a); }).join("");
    box.querySelector(".side-note").textContent = personal ? "読んだ記事に近いキャンペーンです" : "開催中の新着キャンペーンです";
  }
})();
