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

/* ---------- board map: pick a part, see it close up ----------
   Clicking a part on the board (or its legend row) opens the close-up and
   scrolls down to it. A #bm-XX link from a challenge further down the page
   scrolls back up to the board instead, so you see where the part lives. */
(function () {
  var stage = document.querySelector('.bm-stage');
  if (!stage) return;
  var rows   = [].slice.call(document.querySelectorAll('.bm-row'));
  var legs   = [].slice.call(document.querySelectorAll('.bm-leg'));
  var panels = [].slice.call(document.querySelectorAll('.bm-panel'));
  var empty  = document.querySelector('.bm-empty');
  var detail = document.querySelector('.bm-detail');
  var board  = document.getElementById('board');
  var pinned = null;

  function smooth() {
    return matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
  }
  function goTo(el, block) {
    if (el) el.scrollIntoView({ behavior: smooth(), block: block || 'start' });
  }
  function show(ref) {
    rows.forEach(function (r) {
      var on = r.dataset.ref === ref;
      r.classList.toggle('is-active', on);
      r.classList.toggle('is-dim', !!ref && !on);
    });
    legs.forEach(function (l) { l.classList.toggle('is-active', l.dataset.ref === ref); });
    panels.forEach(function (p) { p.hidden = p.dataset.ref !== ref; });
    if (empty) empty.hidden = !!ref;
  }
  function pick(ref, where) {
    pinned = ref;
    show(ref);
    if (ref) history.replaceState(null, '', '#bm-' + ref);
    if (where === 'detail') goTo(detail, 'center');
    else if (where === 'board') goTo(board, 'start');
  }

  stage.addEventListener('mouseover', function (e) {
    var a = e.target.closest('.bm-hot');
    if (a && !pinned) show(a.dataset.ref);
  });
  stage.addEventListener('mouseleave', function () { if (!pinned) show(null); });
  stage.addEventListener('focusin', function (e) {
    var a = e.target.closest('.bm-hot');
    if (a) show(a.dataset.ref);
  });

  // click the part on the board -> open it and scroll to the close-up
  stage.addEventListener('click', function (e) {
    var a = e.target.closest('.bm-hot');
    if (!a) return;
    e.preventDefault();
    pick(pinned === a.dataset.ref ? null : a.dataset.ref, 'detail');
  });

  // click a legend row -> same thing
  legs.forEach(function (l) {
    var a = l.querySelector('a');
    if (!a) return;
    a.addEventListener('click', function (e) { e.preventDefault(); pick(l.dataset.ref, 'detail'); });
  });

  // a #bm-XX link from a challenge -> scroll up to the board itself
  function fromHash() {
    var m = /^#bm-([A-Za-z0-9]+)$/.exec(location.hash || '');
    if (!m) return;
    var ref = m[1];
    if (!panels.some(function (p) { return p.dataset.ref === ref; })) return;
    pinned = ref;
    show(ref);
    goTo(board, 'start');
  }
  addEventListener('hashchange', fromHash);
  fromHash();
})();
