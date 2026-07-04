"""
e.volve BLE scale — body composition capture.

Replicates exactly what nRF Connect did to trigger the body comp measurement:
  1. Subscribe to FFB2 (weight updates)
  2. Subscribe to FFB3 (body composition result)
  3. Write user profile to FFB1
  4. Step on barefoot and grip the handle

All packets are saved to scale_packets.txt.
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from bleak import BleakClient, BleakScanner

LOG_FILE = Path(__file__).parent / "scale_packets.txt"

DEVICE_PREFIX = "e.volve"
SCAN_TIMEOUT = 15
MEASURE_TIMEOUT = 90
IDLE_TIMEOUT = 12

# User profile
USER_HEIGHT_CM = 194
USER_AGE = 34
USER_SEX = 1  # 1 = male
USER_UNIT = 0  # 0 = kg

CHAR_FFB1 = "0000ffb1-0000-1000-8000-00805f9b34fb"
CHAR_FFB2 = "0000ffb2-0000-1000-8000-00805f9b34fb"
CHAR_FFB3 = "0000ffb3-0000-1000-8000-00805f9b34fb"

_log_file = None
_last_packet = 0.0


def emit(text: str) -> None:
    print(text)
    if _log_file:
        _log_file.write(text + "\n")
        _log_file.flush()


def log_packet(label: str, data: bytes) -> None:
    global _last_packet
    _last_packet = time.monotonic()
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    hex_str = " ".join(f"{b:02X}" for b in data)
    interesting = len(data) > 20
    marker = (
        "  *** BODY COMP ***"
        if len(data) == 43
        else ("  *** INTERESTING ***" if interesting else "")
    )
    emit(f"[{ts}] {label}{marker}")
    emit(f"         HEX: {hex_str}")
    emit(f"         LEN: {len(data)} bytes")
    emit("")


def make_handler(label: str):
    def handler(_, data: bytes):
        log_packet(label, data)

    return handler


def build_user_profile() -> bytes:
    h_high = (USER_HEIGHT_CM >> 8) & 0xFF
    h_low = USER_HEIGHT_CM & 0xFF
    body = bytes([0xFE, USER_UNIT, 0x00, USER_AGE, h_high, h_low, USER_SEX])
    checksum = 0
    for b in body:
        checksum ^= b
    return body + bytes([checksum])


async def main() -> None:
    global _log_file, _last_packet
    _log_file = open(LOG_FILE, "w")
    emit(f"=== e.volve capture — {datetime.now().isoformat()} ===\n")

    print(f"Scanning for '{DEVICE_PREFIX}*'…")
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: bool(d.name and d.name.lower().startswith(DEVICE_PREFIX.lower())),
        timeout=SCAN_TIMEOUT,
    )
    if device is None:
        print("ERROR: scale not found. Step on it briefly to wake it up and try again.")
        sys.exit(1)

    print(f"Found: {device.name}  ({device.address})\n")

    async with BleakClient(device) as client:
        print("Connected.\n")

        # Wait for GATT service discovery to complete
        await asyncio.sleep(2.0)

        # Step 1: Subscribe FFB2 (notify)
        await client.start_notify(CHAR_FFB2, make_handler("FFB2"))
        print("  Subscribed: FFB2 (Notify)")

        # Step 2: Subscribe FFB3 (indicate)
        await client.start_notify(CHAR_FFB3, make_handler("FFB3"))
        print("  Subscribed: FFB3 (Indicate)")

        # Brief pause — let scale register subscriptions before we write
        await asyncio.sleep(1.0)

        # Step 3: Send user profile to FFB1 (exactly as nRF Connect did)
        cmd = build_user_profile()
        print(f"\n  Sending to FFB1: {' '.join(f'{b:02X}' for b in cmd)}")
        emit(f"Sent to FFB1: {' '.join(f'{b:02X}' for b in cmd)}\n")
        await client.write_gatt_char(CHAR_FFB1, cmd, response=False)

        print()
        print("━" * 50)
        print("NOW: step on the scale BAREFOOT and HOLD THE HANDLE.")
        print("Stand completely still until it beeps with the full result.")
        print(
            f"Waiting up to {MEASURE_TIMEOUT}s (stops {IDLE_TIMEOUT}s after last packet)."
        )
        print("━" * 50)
        print()

        _last_packet = time.monotonic()
        deadline = time.monotonic() + MEASURE_TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            if time.monotonic() - _last_packet >= IDLE_TIMEOUT:
                print(f"\nNo packets for {IDLE_TIMEOUT}s — done.")
                break

    _log_file.close()
    print(f"\nSaved to {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
