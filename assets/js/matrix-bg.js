/* Minimal matrix flow for the home page.
   Deliberately sparse and dim: wide column spacing, slow cadence and a low
   alpha, so it reads as texture behind the content rather than decoration
   competing with it. Honours prefers-reduced-motion (paints one still frame)
   and stops while the tab is hidden. */
(function () {
  var host = document.getElementById('matrix-bg');
  if (!host || !host.getContext) return;

  var ctx = host.getContext('2d', { alpha: true });
  var GLYPHS = '01ABCDEF<>/\\{}[]*+=_·'.split('');
  var FS = 15;          // glyph size
  var GAP = 2.6;        // column spacing multiplier — higher = sparser
  var cols, drops, step = 95, timer = null, dpr = 1;

  function size() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = host.clientWidth, h = host.clientHeight;
    host.width = Math.floor(w * dpr);
    host.height = Math.floor(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = FS + 'px "IBM Plex Mono", ui-monospace, monospace';
    cols = Math.ceil(w / (FS * GAP));
    drops = [];
    for (var i = 0; i < cols; i++) drops.push(Math.random() * -40);
  }

  function frame() {
    var w = host.clientWidth, h = host.clientHeight;
    // soft trail rather than a hard clear
    ctx.fillStyle = 'rgba(10,10,10,0.10)';
    ctx.fillRect(0, 0, w, h);
    for (var i = 0; i < cols; i++) {
      if (Math.random() > 0.86) continue;          // leave gaps: not every column every frame
      var ch = GLYPHS[(Math.random() * GLYPHS.length) | 0];
      var x = i * FS * GAP, y = drops[i] * FS;
      ctx.fillStyle = Math.random() < 0.05 ? 'rgba(160,240,186,0.40)' : 'rgba(53,193,94,0.17)';
      ctx.fillText(ch, x, y);
      if (y > h && Math.random() > 0.982) drops[i] = Math.floor(Math.random() * -30);
      drops[i]++;
    }
  }

  var reduce = matchMedia('(prefers-reduced-motion: reduce)');
  function run() {
    clearInterval(timer);
    if (reduce.matches) { frame(); return; }       // one still frame, no loop
    timer = setInterval(frame, step);
  }
  function restart() { size(); run(); }

  var rt;
  addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(restart, 180); });
  reduce.addEventListener('change', restart);
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) clearInterval(timer); else run();
  });
  restart();
})();
