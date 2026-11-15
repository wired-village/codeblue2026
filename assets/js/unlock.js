/* Unlock the passphrase-protected walkthroughs.
 *
 * Locked guides ship as ciphertext in a data-k attribute (salt.iv.ct, all base64).
 * The passphrase is never in the page; it derives the key here in the browser via
 * PBKDF2, and AES-GCM either authenticates and decrypts or it doesn't. There is no
 * "correct passphrase" flag to tamper with: a wrong passphrase simply fails to
 * decrypt. ITERATIONS must match tools/lock_guides.py.
 *
 * Once a passphrase works it's kept in sessionStorage for the tab, so a reader
 * unlocks once rather than per challenge. Cleared when the tab closes.
 */
(function () {
  "use strict";
  var ITERATIONS = 600000;
  var KEY = "cmp_guide_pass";

  // sessionStorage throws in some privacy modes / sandboxed iframes - never let that
  // break the unlock flow, it's only a per-tab convenience.
  function ssGet() { try { return sessionStorage.getItem(KEY); } catch (e) { return null; } }
  function ssSet(v) { try { sessionStorage.setItem(KEY, v); } catch (e) { /* ignore */ } }

  function b64(s) {
    var bin = atob(s), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  async function decrypt(blob, pass) {
    var parts = blob.split(".");
    if (parts.length !== 3) throw new Error("bad blob");
    var salt = b64(parts[0]), iv = b64(parts[1]), ct = b64(parts[2]);
    var base = await crypto.subtle.importKey(
      "raw", new TextEncoder().encode(pass), "PBKDF2", false, ["deriveKey"]);
    var key = await crypto.subtle.deriveKey(
      { name: "PBKDF2", salt: salt, iterations: ITERATIONS, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
    var plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: iv }, key, ct);
    return new TextDecoder().decode(plain);
  }

  function reveal(details, html) {
    var body = details.querySelector(".reveal-body");
    body.innerHTML = html;
    details.classList.remove("locked");
    var pill = details.querySelector(".lockpill");
    if (pill) pill.remove();
    details.dataset.k = "";
  }

  async function tryOpen(details, pass, msgEl) {
    try {
      var html = await decrypt(details.dataset.k, pass);
      reveal(details, html);
      ssSet(pass);
      unlockAll(pass);                       // open any others already on the page
      return true;
    } catch (e) {
      if (msgEl) { msgEl.textContent = "That passphrase didn't work."; msgEl.className = "pinmsg bad"; }
      return false;
    }
  }

  async function unlockAll(pass) {
    var nodes = document.querySelectorAll("details.locked[data-k]");
    for (var i = 0; i < nodes.length; i++) {
      var d = nodes[i];
      if (!d.dataset.k) continue;
      try { reveal(d, await decrypt(d.dataset.k, pass)); } catch (e) { /* leave locked */ }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.crypto || !crypto.subtle) {
      // file:// or an ancient browser - WebCrypto needs a secure context
      document.querySelectorAll("details.locked .pinmsg").forEach(function (m) {
        m.textContent = "This browser can't decrypt here (needs an https page).";
        m.className = "pinmsg bad";
      });
      return;
    }

    var saved = ssGet();
    if (saved) unlockAll(saved);

    document.addEventListener("submit", function (ev) {
      var form = ev.target.closest ? ev.target.closest(".pinform") : null;
      if (!form) return;
      ev.preventDefault();
      var details = form.closest("details.locked");
      if (!details) return;
      var input = form.querySelector(".pinin");
      var msg = form.querySelector(".pinmsg");
      var pass = (input.value || "").trim();
      if (!pass) return;
      msg.textContent = "Checking…"; msg.className = "pinmsg";
      tryOpen(details, pass, msg);
    });
  });
})();
