"""
e.volve BLE scale — production ingestion script.

Connects to the e.volve smart scale, waits for a full body composition
reading, decodes the FFB3 packet, and POSTs the data to the Fitman API.

⚠️  Medical disclaimer: Body composition metrics beyond raw weight are
estimates derived from bioelectrical impedance analysis (BIA). The
developers are not medical professionals. These values are not clinically
validated and must not be used for medical diagnosis or treatment. Always
consult a qualified healthcare professional.

Configuration — set in the project .env or as environment variables:
  FITMAN_API_URL      Fitman server base URL  (default: http://localhost:8000)
  ADMIN_USERNAME      Login username           (reuses server .env value)
  ADMIN_PASSWORD      Login password           (plaintext for client use)
  SCALE_AGE           Your age in years
  SCALE_HEIGHT_CM     Your height in cm
  SCALE_SEX           1 = male, 0 = female

Usage:
  source backend/.venv/bin/activate
  python scripts/scale_ingest.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

import httpx
from bleak import BleakClient, BleakScanner
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# ── Config ────────────────────────────────────────────────────────────────────

API_URL = os.getenv("FITMAN_API_URL", "http://localhost:8000")
USERNAME = os.getenv("ADMIN_USERNAME", "")
PASSWORD = os.getenv("ADMIN_PASSWORD", "")

SCALE_AGE = int(os.getenv("SCALE_AGE", "0"))
SCALE_HEIGHT_CM = int(os.getenv("SCALE_HEIGHT_CM", "0"))
SCALE_SEX = int(os.getenv("SCALE_SEX", "1"))  # 1=male, 0=female

DEVICE_PREFIX = "e.volve"
SCAN_TIMEOUT = 15
MEASURE_TIMEOUT = 90
IDLE_TIMEOUT = 12

CHAR_FFB1 = "0000ffb1-0000-1000-8000-00805f9b34fb"
CHAR_FFB2 = "0000ffb2-0000-1000-8000-00805f9b34fb"
CHAR_FFB3 = "0000ffb3-0000-1000-8000-00805f9b34fb"


# ── Packet decoding ───────────────────────────────────────────────────────────


def decode_ffb3(data: bytes) -> dict:
    """Decode 43-byte FFB3 body composition packet into measurement fields."""
    if len(data) != 43:
        return {}
    return {
        "weight_kg": round((data[8] * 256 + data[9] + 65536) / 1000, 3),
        "body_fat_pct": int.from_bytes(data[40:42], "big") / 10,
        "ra_z20": int.from_bytes(data[16:18], "little") / 10,
        "la_z20": int.from_bytes(data[18:20], "little") / 10,
        "rl_z20": int.from_bytes(data[20:22], "little") / 10,
        "ll_z20": int.from_bytes(data[22:24], "little") / 10,
        "trunk_z20": float(data[24]),
        "ra_z100": int.from_bytes(data[26:28], "little") / 10,
        "la_z100": int.from_bytes(data[28:30], "little") / 10,
        "rl_z100": int.from_bytes(data[30:32], "little") / 10,
        "ll_z100": int.from_bytes(data[32:34], "little") / 10,
        "trunk_z100": float(data[35]),
    }


def build_user_profile() -> bytes:
    h_high = (SCALE_HEIGHT_CM >> 8) & 0xFF
    h_low = SCALE_HEIGHT_CM & 0xFF
    body = bytes([0xFE, 0x00, 0x00, SCALE_AGE, h_high, h_low, SCALE_SEX])
    checksum = 0
    for b in body:
        checksum ^= b
    return body + bytes([checksum])


# ── API ───────────────────────────────────────────────────────────────────────


async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{API_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def post_measurement(client: httpx.AsyncClient, token: str, data: dict) -> dict:
    resp = await client.post(
        f"{API_URL}/api/measurements",
        json=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


# ── BLE ───────────────────────────────────────────────────────────────────────


async def main() -> None:
    _validate_config()

    print(f"Scanning for '{DEVICE_PREFIX}*'…")
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: bool(d.name and d.name.lower().startswith(DEVICE_PREFIX.lower())),
        timeout=SCAN_TIMEOUT,
    )
    if device is None:
        print("ERROR: scale not found. Step on it briefly to wake it up and try again.")
        sys.exit(1)

    print(f"Found: {device.name}  ({device.address})")

    body_comp_event = asyncio.Event()
    ffb3_packet: list[bytes] = []

    def on_ffb3(_, data: bytes) -> None:
        if len(data) == 43 and not body_comp_event.is_set():
            ffb3_packet.append(data)
            body_comp_event.set()

    async with BleakClient(device) as client:
        print("Connected.")
        await asyncio.sleep(2.0)

        await client.start_notify(CHAR_FFB2, lambda _, __: None)
        await client.start_notify(CHAR_FFB3, on_ffb3)
        await asyncio.sleep(1.0)

        cmd = build_user_profile()
        await client.write_gatt_char(CHAR_FFB1, cmd, response=False)

        print()
        print("━" * 50)
        print("Step on the scale BAREFOOT and grip the handle bar.")
        print("Stand still until it beeps and shows the full result.")
        print("━" * 50)
        print()

        try:
            await asyncio.wait_for(body_comp_event.wait(), timeout=MEASURE_TIMEOUT)
        except asyncio.TimeoutError:
            print(f"ERROR: no body comp reading in {MEASURE_TIMEOUT}s. Try again.")
            sys.exit(1)

    packet = ffb3_packet[0]
    measurement = decode_ffb3(packet)
    measurement["recorded_at"] = datetime.now(timezone.utc).isoformat()
    measurement["height_cm"] = float(SCALE_HEIGHT_CM)

    print(f"Weight:    {measurement['weight_kg']} kg")
    print(f"Body fat:  {measurement['body_fat_pct']} %")
    print(f"Trunk Z20: {measurement['trunk_z20']} Ω")
    print()
    print(f"Posting to {API_URL}…")

    async with httpx.AsyncClient() as http:
        token = await get_token(http)
        result = await post_measurement(http, token, measurement)

    print(f"Saved — measurement ID {result['id']}  ({result['recorded_at']})")


def _validate_config() -> None:
    missing = []
    if not USERNAME:
        missing.append("ADMIN_USERNAME")
    if not PASSWORD:
        missing.append("ADMIN_PASSWORD")
    if not SCALE_AGE:
        missing.append("SCALE_AGE")
    if not SCALE_HEIGHT_CM:
        missing.append("SCALE_HEIGHT_CM")
    if missing:
        print(f"ERROR: Missing required config: {', '.join(missing)}")
        print("Set these in the project .env file or as environment variables.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
