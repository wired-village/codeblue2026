// Wired Village — shared site behaviour (no frameworks)
document.addEventListener("DOMContentLoaded", function () {
  // if the URL points at a <details> element (a collapsed section or a
  // challenge's hint/guide), open it and scroll to it
  if (location.hash && location.hash.length > 1) {
    // getElementById avoids querySelector throwing on hashes that aren't valid CSS
    // selectors (bare "#", ids starting with a digit, ids containing spaces, etc.)
    var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (target && target.tagName === "DETAILS") {
      target.open = true;
      setTimeout(function () { target.scrollIntoView({ behavior: "smooth", block: "start" }); }, 50);
    }
  }

  // whole-row navigation for index-table rows marked with data-href
  document.querySelectorAll("tr[data-href]").forEach(function (row) {
    row.addEventListener("click", function (e) {
      if (e.target.closest("a")) return; // let a real link inside still work normally
      window.location.href = row.getAttribute("data-href");
    });
  });
});

/* ---------- board map: select a part, show its pinout ----------
   Hover previews, click/Enter pins the selection, and a #bm-XX hash
   (used by the "see it on the board map" links further down each page)
   scrolls here and selects that part. */
(function () {
  var stage = document.querySelector('.bm-stage');
  if (!stage) return;
  var rows    = [].slice.call(document.querySelectorAll('.bm-row'));
  var panels  = [].slice.call(document.querySelectorAll('.bm-panel'));
  var empty   = document.querySelector('.bm-empty');
  var pinned  = null;

  function show(ref) {
    var any = false;
    rows.forEach(function (r) {
      var on = r.dataset.ref === ref;
      r.classList.toggle('is-active', on);
      r.classList.toggle('is-dim', !!ref && !on && r.classList.contains('is-interactive') === false ? false : (!!ref && !on));
      if (on) any = true;
    });
    panels.forEach(function (p) { p.hidden = p.dataset.ref !== ref; });
    if (empty) empty.hidden = !!ref && any;
    if (!ref) { rows.forEach(function (r) { r.classList.remove('is-dim', 'is-active'); }); }
  }

  stage.addEventListener('mouseover', function (e) {
    var a = e.target.closest('.bm-hot'); if (!a || pinned) return;
    show(a.dataset.ref);
  });
  stage.addEventListener('mouseleave', function () { if (!pinned) show(null); });
  stage.addEventListener('focusin', function (e) {
    var a = e.target.closest('.bm-hot'); if (a) show(a.dataset.ref);
  });
  stage.addEventListener('click', function (e) {
    var a = e.target.closest('.bm-hot'); if (!a) return;
    e.preventDefault();
    pinned = (pinned === a.dataset.ref) ? null : a.dataset.ref;
    show(pinned);
    if (pinned) history.replaceState(null, '', '#bm-' + pinned);
  });

  function fromHash() {
    var m = /^#bm-([A-Za-z0-9]+)$/.exec(location.hash || '');
    if (!m) return;
    var ref = m[1];
    if (!panels.some(function (p) { return p.dataset.ref === ref; })) return;
    pinned = ref; show(ref);
    var el = document.getElementById('board');
    if (el) el.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  }
  addEventListener('hashchange', fromHash);
  fromHash();
})();
