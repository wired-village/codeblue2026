#!/usr/bin/env python3
"""Satellite Level 3 -- open-source firmware download.

Unlike download.py (Level 5), this one isn't triggered by typing a
command: the badge starts sending the moment the player presses OK on its
own "Download Open-Source Firmware" prompt. Run this first, then press OK
on the badge -- it just waits and saves whatever arrives.

    python download_firmware_source.py [port]

Saves the satellite's own receive-handler source (sim_rx.cpp +
satellite_sim.cpp, concatenated) to your home directory as
satellite_firmware_source.txt. Read it to find the Level 3 diagnostic
request's opcode, argument bytes, and checksum formula.
"""
import os
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
OUT_PATH = os.path.join(os.path.expanduser("~"), "satellite_firmware_source.txt")

print(f"Waiting for the download on {PORT} -- press OK on the badge's "
      f"\"Download Open-Source Firmware\" prompt now.")

with serial.Serial(PORT, 115200, timeout=2) as s:
    time.sleep(0.3)
    s.reset_input_buffer()

    hex_chunks, capturing, expected = [], False, 0
    deadline = time.time() + 120
    while time.time() < deadline:
        line = s.readline().decode(errors="replace").strip()
        if not line:
            continue
        if line.startswith("FCSRC_BEGIN"):
            capturing = True
            expected = int(line.split()[1])
            print(f"Receiving {expected} bytes...")
            continue
        if line.startswith("FCSRC_END"):
            break
        if capturing:
            hex_chunks.append(line)
        else:
            print(line)

if not hex_chunks:
    sys.exit("No download received -- did you press OK on the badge's download prompt?")

data = bytes.fromhex("".join(hex_chunks))
if expected and len(data) != expected:
    print(f"WARNING: expected {expected} bytes, got {len(data)}")

with open(OUT_PATH, "wb") as f:
    f.write(data)
print(f"Saved {OUT_PATH} ({len(data)} bytes)")
