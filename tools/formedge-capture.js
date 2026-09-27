/* FormEdge page capture — a bookmarklet that saves what YOU are viewing.
 *
 * It runs inside your normal browser session, on the page you already opened
 * as a human. It does not crawl, does not solve challenges, and does not touch
 * the site's servers beyond what your browser already loaded: it simply sends
 * the page (or your selection) to your OWN local FormEdge API, which imports it
 * through the normal pipeline.
 *
 * Setup
 * -----
 * 1. Allow the origin you browse from in the API's CORS list. In .env:
 *      CORS_ORIGINS=http://localhost:3000,https://www.mtcjockeyclub.com
 *    (Add whichever site you capture from. Restart the API afterwards.)
 * 2. Get an admin token:
 *      curl -X POST http://127.0.0.1:8000/api/auth/login \
 *        -H "Content-Type: application/json" \
 *        -d '{"email":"admin@example.com","password":"admin1234"}'
 * 3. Create a bookmark whose URL is the single-line form below (everything from
 *    `javascript:` onwards, on one line). Easiest: paste this file's contents
 *    into an online "bookmarklet minifier", or use the one-liner in
 *    docs/data-sourcing-options.md.
 *
 * Usage
 * -----
 * - Select a stats/race table on the page, then click the bookmark → the
 *   selection is sent as tab-separated data (parsed like a CSV).
 * - Click the bookmark with nothing selected → the whole page HTML is sent and
 *   the defensive HTML parsers are used.
 * - First run prompts for the API URL and token; both are cached in
 *   localStorage. A 401 clears the cache so the next click re-prompts.
 */
(function () {
  var KEY = "formedge_capture";
  var cfg;
  try {
    cfg = JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch (e) {
    cfg = {};
  }

  var api = cfg.api || prompt("FormEdge API base URL", "http://127.0.0.1:8000");
  if (!api) return;
  var token = cfg.token || prompt("Paste your FormEdge admin token (JWT)");
  if (!token) return;
  localStorage.setItem(KEY, JSON.stringify({ api: api, token: token }));

  var selection = String(window.getSelection ? window.getSelection() : "").trim();
  var isSelection = selection.length > 0;
  var body = isSelection ? selection : document.documentElement.outerHTML;
  var contentType = isSelection ? "text/csv" : "text/html";
  var safeTitle = (document.title || "page").replace(/[^A-Za-z0-9._-]+/g, "_").slice(0, 60);
  var filename = safeTitle + (isSelection ? "_selection.tsv" : ".html");

  fetch(api.replace(/\/$/, "") + "/api/admin/import?kind=auto", {
    method: "POST",
    headers: {
      "Content-Type": contentType,
      "X-Filename": filename,
      Authorization: "Bearer " + token,
    },
    body: body,
  })
    .then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    })
    .then(function (res) {
      if (res.status === 401 || res.status === 403) {
        localStorage.removeItem(KEY); // force re-auth next time
      }
      var summary = res.data && res.data.warnings ? res.data.warnings : res.data;
      alert(
        "FormEdge import " + (res.ok ? "OK" : "FAILED (HTTP " + res.status + ")") +
          "\nSent: " + filename + " (" + body.length + " chars)\n\n" +
          JSON.stringify(summary, null, 2).slice(0, 700)
      );
    })
    .catch(function (err) {
      alert("FormEdge import error: " + err + "\nCheck the API is running and CORS_ORIGINS includes " + location.origin);
    });
})();
