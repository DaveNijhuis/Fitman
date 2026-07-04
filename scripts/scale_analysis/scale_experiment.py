"""
e.volve BLE scale — controlled byte experiment.

Varies the user profile sent to the scale to identify which unknown
FFB3 bytes correspond to which body metrics.

Usage:
    python scripts/scale_experiment.py --height 194 --age 34 --sex male --label baseline
    python scripts/scale_experiment.py --height 194 --age 34 --sex female --label sex_female
    python scripts/scale_experiment.py --height 170 --age 34 --sex male --label height_170
    python scripts/scale_experiment.py --height 194 --age 60 --sex male --label age_60

Results are appended to scale_experiment_results.json.
Run compare at the end:
    python scripts/scale_experiment.py --compare
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from bleak import BleakClient, BleakScanner

RESULTS_FILE = Path(__file__).parent / "scale_experiment_results.json"

DEVICE_PREFIX = "e.volve"
SCAN_TIMEOUT = 30
STABLE_COUNT = 8

CHAR_FFB1 = "0000ffb1-0000-1000-8000-00805f9b34fb"
CHAR_FFB2 = "0000ffb2-0000-1000-8000-00805f9b34fb"
CHAR_FFB3 = "0000ffb3-0000-1000-8000-00805f9b34fb"


def build_profile(height_cm: int, age: int, sex: int, unit: int = 0) -> bytes:
    h_hi = (height_cm >> 8) & 0xFF
    h_lo = height_cm & 0xFF
    body = bytes([0xFE, unit, 0x00, age, h_hi, h_lo, sex])
    cs = 0
    for b in body:
        cs ^= b
    return body + bytes([cs])


def decode_weight(data: bytes) -> float:
    return (data[8] * 256 + data[9] + 65536) / 1000


def decode_body_fat(data: bytes) -> float:
    return data[41] / 10


def unknown_bytes(data: bytes) -> dict:
    return {
        "b24": data[24],
        "b34_35": list(data[34:36]),
        "b36": data[36],
        "b37": data[37],
        "b38_39": list(data[38:40]),
        "b41": data[41],
    }


async def capture_one(height: int, age: int, sex: int, label: str) -> dict | None:
    print(f"\nScanning for scale… ({label})")
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: bool(d.name and d.name.lower().startswith(DEVICE_PREFIX.lower())),
        timeout=SCAN_TIMEOUT,
    )
    if device is None:
        print("Scale not found.")
        return None

    print(f"Found: {device.name} — connecting…")

    body_comp_evt = asyncio.Event()
    ffb2_stable_evt = asyncio.Event()
    weight_val = [0.0]
    ffb3_packet = [None]

    last_key = None
    streak = 0

    def on_ffb2(_, data: bytes) -> None:
        nonlocal last_key, streak
        if len(data) < 10 or data[7] != 0x61:
            return
        key = bytes(data[7:11])
        if key == last_key:
            streak += 1
        else:
            streak = 1
        last_key = key
        if streak >= STABLE_COUNT and not ffb2_stable_evt.is_set():
            weight_val[0] = decode_weight(data)
            ffb2_stable_evt.set()

    def on_ffb3(_, data: bytes) -> None:
        if len(data) == 43 and not body_comp_evt.is_set():
            ffb3_packet[0] = bytes(data)
            body_comp_evt.set()

    async with BleakClient(device) as client:
        await client.start_notify(CHAR_FFB2, on_ffb2)
        await client.start_notify(CHAR_FFB3, on_ffb3)
        await asyncio.sleep(0.5)

        cmd = build_profile(height, age, sex)
        print(
            f"Sending profile: height={height}cm age={age} sex={'M' if sex == 1 else 'F'}"
        )
        print(f"Command: {' '.join(f'{b:02X}' for b in cmd)}")
        await client.write_gatt_char(CHAR_FFB1, cmd, response=False)

        print("Stand on scale, grab handle, wait for body comp…")

        try:
            await asyncio.wait_for(body_comp_evt.wait(), timeout=90)
        except asyncio.TimeoutError:
            print("Timed out waiting for body comp packet.")
            return None

    data = ffb3_packet[0]
    weight = weight_val[0]
    fat = decode_body_fat(data)

    print(f"\n  Weight:    {weight} kg")
    print(f"  Body fat:  {fat}%")
    print(f"  Full FFB3: {' '.join(f'{b:02X}' for b in data)}")
    print("\n  Unknown bytes:")
    ub = unknown_bytes(data)
    for k, v in ub.items():
        print(f"    {k}: {v}")

    return {
        "label": label,
        "time": datetime.now().isoformat(),
        "profile": {"height_cm": height, "age": age, "sex": sex},
        "weight_kg": weight,
        "body_fat_pct": fat,
        "ffb3_hex": data.hex(),
        "ffb3": list(data),
        "unknowns": ub,
    }


def compare_results() -> None:
    if not RESULTS_FILE.exists():
        print("No results file found.")
        return

    with open(RESULTS_FILE) as f:
        all_results = json.load(f)

    # Group by label
    by_label: dict[str, list] = {}
    for r in all_results:
        by_label.setdefault(r["label"], []).append(r)

    labels = list(by_label.keys())
    print(f"\n{'Metric':<20}", end="")
    for label in labels:
        print(f"  {label:<20}", end="")
    print()
    print("─" * (20 + 22 * len(labels)))

    # Show known bytes
    known = [
        ("weight_kg", lambda r: f"{r['weight_kg']} kg"),
        ("body_fat_%", lambda r: f"{r['body_fat_pct']}%"),
    ]
    for name, fn in known:
        print(f"  {name:<18}", end="")
        for label in labels:
            val = fn(by_label[label][-1])
            print(f"  {val:<20}", end="")
        print()

    print()

    # Show unknown bytes
    uk_keys = ["b24", "b34_35", "b36", "b37", "b38_39"]
    for k in uk_keys:
        print(f"  {k:<18}", end="")
        prev_val = None
        for label in labels:
            val = by_label[label][-1]["unknowns"][k]
            changed = " ←" if prev_val is not None and val != prev_val else ""
            print(f"  {str(val):<18}{changed}", end="")
            prev_val = val
        print()


async def main(args: argparse.Namespace) -> None:
    if args.compare:
        compare_results()
        return

    sex = 1 if args.sex.lower() in ("male", "m", "1") else 0
    result = await capture_one(args.height, args.age, sex, args.label)

    if result:
        existing = []
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE) as f:
                existing = json.load(f)
        existing.append(result)
        with open(RESULTS_FILE, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"\nSaved to {RESULTS_FILE}")
        print("Step off and let it sleep, then run the next configuration.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--height", type=int, default=194)
    parser.add_argument("--age", type=int, default=34)
    parser.add_argument("--sex", type=str, default="male")
    parser.add_argument("--label", type=str, default="test")
    parser.add_argument("--compare", action="store_true")
    asyncio.run(main(parser.parse_args()))
