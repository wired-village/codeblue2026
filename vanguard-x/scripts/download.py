#!/usr/bin/env python3
"""Mission Control -- Satellite Level 5 recon-photo payload download.

Asks the badge for the gzip-compressed recon photo it received from the
satellite and saves it as payload.bin.

    python download.py [port]

Then:
    gunzip -k payload.bin          -> payload (16384 raw bytes = 128*128)
    python3 -c "from PIL import Image; Image.frombytes('L', (128,128), \\
        open('payload','rb').read()).save('mission.png')"
and open mission.png to read the flag rendered on it.
"""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM2"

# A few hundred KB of hex text over a 115200 baud serial line takes a while
# -- generous deadline so the transfer isn't cut off partway through.
with serial.Serial(PORT, 115200, timeout=2) as s:
    time.sleep(0.3)
    s.reset_input_buffer()
    s.write(b"DOWNLOAD\n")

    hex_chunks, capturing, expected = [], False, 0
    deadline = time.time() + 300
    while time.time() < deadline:
        line = s.readline().decode(errors="replace").strip()
        if not line:
            continue
        if line.startswith("PAYLOAD_BEGIN"):
            capturing = True
            expected = int(line.split()[1])
            print(f"Receiving {expected} bytes...")
            continue
        if line.startswith("PAYLOAD_END"):
            break
        if capturing:
            hex_chunks.append(line)
        else:
            print(line)

if not hex_chunks:
    sys.exit("No payload received. Is the transfer complete on the badge?")

data = bytes.fromhex("".join(hex_chunks))
if expected and len(data) != expected:
    print(f"WARNING: expected {expected} bytes, got {len(data)}")

with open("payload.bin", "wb") as f:
    f.write(data)
print(f"Saved payload.bin ({len(data)} bytes)")
print(f"First bytes: {data[:4].hex(' ')}  (1f 8b = gzip magic)")
