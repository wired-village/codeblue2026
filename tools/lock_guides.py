#!/usr/bin/env python3
"""Encrypt the later challenges' walkthroughs behind a passphrase.

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
  GUIDE_PIN='...' python3 tools/lock_guides.py --status   # report, change nothing

Re-running is safe: already-locked blocks are skipped. To rotate the passphrase,
--unlock with the old one, then run again with the new one (locking discards the
plaintext from the repo, so --unlock is the only way back).

How much stays open
-------------------
Counted by *challenge*, not by guide block: the first FREE_CHALLENGES challenges
on a page keep their guides open, every challenge after that has its guides
locked. That matters because a Sysrupt challenge carries several progressive
hint blocks, so counting raw blocks would lock part-way through challenge one.
A challenge is a `<div class="entry" id="c6">` or `id="ch06">`. An entry with any other id -
the Sysrupt V2 "initial-access" prologue, for instance - is treated as framing
rather than a challenge: it never consumes a free slot and its guides are never
locked.

Only *top-level* guide blocks are locked. A guide block nested inside another
one is left alone and travels with its parent's ciphertext - otherwise the
Sysrupt V2 walkthroughs, which carry inline hint blocks inside the wrapper,
would be encrypted twice over.
"""
import os, re, sys, base64, hashlib, secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 600_000          # must match assets/js/unlock.js
FREE_CHALLENGES = 3           # first N challenges of each page stay open

PAGES = [
    'compatriot/automotive.html',
    'compatriot/embedded.html',
    'compatriot/wireless.html',
    'sysrupt/challenges.html',
    'sysrupt-v2/challenges.html',
]

OPEN_TAG = '<details class="reveal guide">'
LOCK_PILL = '<span class="lockpill">locked</span>'

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


# --------------------------------------------------------------- HTML scanning
_DET = re.compile(r'<details\b|</details>', re.I)


def match_close(html: str, open_start: int) -> int:
    """Index just past the </details> that closes the <details> at open_start.

    Depth-counted rather than regex'd, so a block containing nested <details>
    is matched as a whole instead of stopping at the first inner close.
    """
    depth = 0
    for m in _DET.finditer(html, open_start):
        if m.group(0).lower().startswith('</'):
            depth -= 1
            if depth == 0:
                return m.end()
        else:
            depth += 1
    raise ValueError(f'unclosed <details> at offset {open_start}')


def find_blocks(html: str, tag: str):
    """Top-level occurrences of `tag`, as (start, end). Nested ones are skipped."""
    out, pos = [], 0
    while True:
        i = html.find(tag, pos)
        if i < 0:
            return out
        end = match_close(html, i)
        out.append((i, end))
        pos = end            # anything inside this block is nested: skip past it


# Challenge ids differ per page: the Compatriot pages number them c1..c6, the
# Sysrupt pages ch01..ch10. Anything else (a prologue, a framing block) is not
# a challenge.
CHALLENGE_ID = re.compile(r'^ch?\d+$')


def entry_offsets(html: str):
    """Every `<div class="entry" id="...">` as (offset, id), in document order."""
    return [(m.start(), m.group(1))
            for m in re.finditer(r'<div class="entry"[^>]*\bid="([^"]+)"', html)]


def challenge_index(entries, pos: int) -> int:
    """Index of the challenge containing `pos`, counting only real chNN entries.

    Returns -1 when `pos` is outside any entry, or inside one that is not a
    numbered challenge - both of which mean "leave it open".
    """
    here = None
    seen = -1
    for off, eid in entries:
        if off > pos:
            break
        if CHALLENGE_ID.match(eid):
            seen += 1
            here = seen
        else:
            here = -1          # inside a prologue / framing entry
    return here if here is not None else -1


def split_block(block: str):
    """-> (summary_inner_html, body_inner_html) or None if it is not lockable."""
    m = re.match(r'<details class="reveal guide">\s*<summary>(.*?)</summary>\s*'
                 r'<div class="reveal-body">(.*)</div>\s*</details>\s*$', block, re.DOTALL)
    if not m:
        return None
    return m.group(1), m.group(2)


# ------------------------------------------------------------------- operations
def do_unlock(root, pin) -> int:
    restored = 0
    for rel in PAGES:
        path = os.path.join(root, rel)
        html = open(path, encoding='utf-8').read()
        blocks = find_blocks(html, '<details class="reveal guide locked"')
        if not blocks:
            print(f'{rel}: nothing locked')
            continue
        out, cursor, here = [], 0, 0
        for start, end in blocks:
            chunk = html[start:end]
            m = re.match(r'<details class="reveal guide locked" data-k="([^"]+)">\s*'
                         r'<summary>(.*?)</summary>', chunk, re.DOTALL)
            if not m:
                out.append(html[cursor:end]); cursor = end
                print(f'{rel}: a locked block had an unexpected shape, left alone',
                      file=sys.stderr)
                continue
            try:
                body = decrypt(m.group(1), pin)
            except Exception:
                out.append(html[cursor:end]); cursor = end
                print(f'{rel}: wrong passphrase for one block, left locked', file=sys.stderr)
                continue
            summary = m.group(2).replace(LOCK_PILL, '').strip()
            out.append(html[cursor:start])
            out.append(f'{OPEN_TAG}<summary>{summary}</summary>'
                       f'<div class="reveal-body">{body}</div></details>')
            cursor = end
            here += 1
        out.append(html[cursor:])
        open(path, 'w', encoding='utf-8').write(''.join(out))
        restored += here
        print(f'{rel}: unlocked {here}')
    print(f'\nrestored {restored} guides to plaintext')
    return 0


def do_lock(root, pin, verify) -> int:
    total = 0
    for rel in PAGES:
        path = os.path.join(root, rel)
        html = open(path, encoding='utf-8').read()
        entries = entry_offsets(html)
        already = len(find_blocks(html, '<details class="reveal guide locked"'))
        blocks = find_blocks(html, OPEN_TAG)

        # which challenges are free, and which open blocks belong to a locked one
        to_lock, skipped = [], 0
        for start, end in blocks:
            ci = challenge_index(entries, start)
            if ci < 0 or ci < FREE_CHALLENGES:
                continue
            if split_block(html[start:end]) is None:
                skipped += 1
                continue
            to_lock.append((start, end))

        if not to_lock:
            note = f' ({already} already locked)' if already else ''
            extra = f', {skipped} not lockable' if skipped else ''
            print(f'{rel}: nothing to lock{note}{extra}')
            continue

        out, cursor, here = [], 0, 0
        for start, end in to_lock:
            summary, body = split_block(html[start:end])
            blob = encrypt(body, pin)
            if verify and decrypt(blob, pin) != body:
                print(f'{rel}: round-trip FAILED at offset {start}', file=sys.stderr)
                return 1
            out.append(html[cursor:start])
            out.append(f'<details class="reveal guide locked" data-k="{blob}">'
                       f'<summary>{summary} {LOCK_PILL}</summary>'
                       f'<div class="reveal-body">{LOCK_FORM}</div></details>')
            cursor = end
            here += 1
        out.append(html[cursor:])
        open(path, 'w', encoding='utf-8').write(''.join(out))
        total += here
        nch = sum(1 for _, eid in entries if CHALLENGE_ID.match(eid))
        print(f'{rel}: {nch} challenges, first {min(FREE_CHALLENGES, nch)} open, '
              f'{here} guides locked'
              + (f', {skipped} not lockable (no reveal-body)' if skipped else ''))

    print(f'\nlocked {total} guides with PBKDF2 x{ITERATIONS:,} + AES-256-GCM')
    if verify:
        print('round-trip verified on every locked block')
    return 0


def do_status(root) -> int:
    for rel in PAGES:
        path = os.path.join(root, rel)
        html = open(path, encoding='utf-8').read()
        entries = entry_offsets(html)
        locked = find_blocks(html, '<details class="reveal guide locked"')
        openb = find_blocks(html, OPEN_TAG)
        per = {}
        for start, _ in openb:
            per.setdefault(challenge_index(entries, start), [0, 0])[0] += 1
        for start, _ in locked:
            per.setdefault(challenge_index(entries, start), [0, 0])[1] += 1
        nch = sum(1 for _, eid in entries if CHALLENGE_ID.match(eid))
        print(f'{rel}: {nch} challenges, {len(openb)} open, {len(locked)} locked')
        for ci in sorted(per):
            o, l = per[ci]
            if ci < 0:
                print(f'    (framing, always open)  open={o} locked={l}')
                continue
            label = 'free' if ci < FREE_CHALLENGES else 'locked'
            print(f'    challenge {ci + 1:>2} [{label:>6}]  open={o} locked={l}')
    return 0


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if '--status' in sys.argv:
        return do_status(root)

    pin = os.environ.get('GUIDE_PIN')
    if not pin:
        print('error: set GUIDE_PIN in the environment (it is never written to disk)',
              file=sys.stderr)
        return 2

    if '--unlock' in sys.argv:
        return do_unlock(root, pin)
    return do_lock(root, pin, '--verify' in sys.argv)


if __name__ == '__main__':
    sys.exit(main())
