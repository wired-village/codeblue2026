#!/usr/bin/env python3
"""Encrypt the 'Full guide' bodies of the later challenges behind a passphrase.

The site is static (GitHub Pages), so there is no server to check a PIN against.
Rather than a JavaScript equality check - which would put the PIN in the page
source and protect nothing - each locked guide body is encrypted here at build
time and only the ciphertext is committed. The passphrase itself never enters
the repository.

  PBKDF2-HMAC-SHA256(passphrase, salt, ITERATIONS) -> 256-bit key
  AES-256-GCM(key, iv) -> ciphertext (auth tag appended, as WebCrypto expects)

Honest limitation: the ciphertext is public, so the passphrase can be attacked
offline. The iteration count below makes each guess expensive, but a short or
dictionary passphrase is still crackable. Use something random-ish.

Usage:
  GUIDE_PIN='...' python3 tools/lock_guides.py            # encrypt
  GUIDE_PIN='...' python3 tools/lock_guides.py --verify   # check round-trip
  GUIDE_PIN='...' python3 tools/lock_guides.py --unlock   # decrypt back in place

Re-running is safe: already-locked blocks are skipped. To rotate the passphrase,
--unlock with the old one, then run again with the new one (locking discards the
plaintext from the repo, so --unlock is the only way back).
"""
import os, re, sys, base64, hashlib, secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 600_000          # must match assets/js/unlock.js
FREE_PER_CATEGORY = 3         # first N challenges of each category stay open

PAGES = [
    'compatriot/automotive.html',
    'compatriot/embedded.html',
    'compatriot/wireless.html',
]

GUIDE_RE = re.compile(
    r'<details class="reveal guide"><summary>Full guide</summary><div class="reveal-body">(.*?)</div></details>',
    re.DOTALL)

LOCK_FORM = (
    '<form class="pinform" autocomplete="off">'
    '<p class="pinlead">This walkthrough is locked. Enter the passphrase given at the event to open it.</p>'
    '<div class="pinrow">'
    '<input type="password" class="pinin" placeholder="passphrase" '
    'autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" '
    'aria-label="passphrase">'
    '<button type="submit" class="pinbtn">Unlock</button>'
    '</div>'
    '<p class="pinmsg" role="status"></p>'
    '</form>')


def encrypt(plaintext: str, passphrase: str) -> str:
    salt = secrets.token_bytes(16)
    iv = secrets.token_bytes(12)
    key = hashlib.pbkdf2_hmac('sha256', passphrase.encode(), salt, ITERATIONS, 32)
    ct = AESGCM(key).encrypt(iv, plaintext.encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return f'{b64(salt)}.{b64(iv)}.{b64(ct)}'


def decrypt(blob: str, passphrase: str) -> str:
    s, i, c = (base64.b64decode(p) for p in blob.split('.'))
    key = hashlib.pbkdf2_hmac('sha256', passphrase.encode(), s, ITERATIONS, 32)
    return AESGCM(key).decrypt(i, c, None).decode()


def main() -> int:
    pin = os.environ.get('GUIDE_PIN')
    if not pin:
        print('error: set GUIDE_PIN in the environment (it is never written to disk)',
              file=sys.stderr)
        return 2
    verify = '--verify' in sys.argv
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if '--unlock' in sys.argv:
        restored = 0
        for rel in PAGES:
            path = os.path.join(root, rel)
            html = open(path, encoding='utf-8').read()
            def back(m):
                nonlocal restored
                try:
                    body = decrypt(m.group(1), pin)
                except Exception:
                    print(f'{rel}: wrong passphrase for one block, left locked', file=sys.stderr)
                    return m.group(0)
                restored += 1
                return ('<details class="reveal guide"><summary>Full guide</summary>'
                        f'<div class="reveal-body">{body}</div></details>')
            html2 = re.sub(
                r'<details class="reveal guide locked" data-k="([^"]+)">.*?</details>',
                back, html, flags=re.DOTALL)
            open(path, 'w', encoding='utf-8').write(html2)
            print(f'{rel}: unlocked')
        print(f'\nrestored {restored} guides to plaintext')
        return 0

    total_locked = 0
    for rel in PAGES:
        path = os.path.join(root, rel)
        html = open(path, encoding='utf-8').read()
        blocks = list(GUIDE_RE.finditer(html))
        already = html.count('class="reveal guide locked"')
        if not blocks:
            print(f'{rel}: nothing to lock ({already} already locked)')
            continue

        out, cursor, idx, locked_here = [], 0, 0, 0
        for m in blocks:
            idx += 1
            out.append(html[cursor:m.start()])
            if idx <= FREE_PER_CATEGORY:
                out.append(m.group(0))            # leave the first N open
            else:
                blob = encrypt(m.group(1), pin)
                if verify and decrypt(blob, pin) != m.group(1):
                    print(f'{rel}: round-trip FAILED on guide #{idx}', file=sys.stderr)
                    return 1
                out.append(
                    f'<details class="reveal guide locked" data-k="{blob}">'
                    f'<summary>Full guide <span class="lockpill">locked</span></summary>'
                    f'<div class="reveal-body">{LOCK_FORM}</div></details>')
                locked_here += 1
            cursor = m.end()
        out.append(html[cursor:])
        open(path, 'w', encoding='utf-8').write(''.join(out))
        total_locked += locked_here
        print(f'{rel}: {idx} guides, {min(idx, FREE_PER_CATEGORY)} open, {locked_here} locked')

    print(f'\nlocked {total_locked} guides with PBKDF2 x{ITERATIONS:,} + AES-256-GCM')
    if verify:
        print('round-trip verified on every locked block')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
