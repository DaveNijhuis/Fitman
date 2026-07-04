"""
e.volve BLE scale — weight calibration.

The scale powers down between measurements, so this script reconnects
automatically each time. Flow per measurement:
  1. Scale wakes up (you step on) → script connects
  2. Weight stabilises → prints the bytes
  3. You type what the display shows
  4. Scale powers off → connection drops → script waits for next one

Press Ctrl+C when done. Results + formula printed at exit.
"""

import asyncio
from bleak import BleakClient, BleakScanner

DEVICE_PREFIX = "e.volve"
SCAN_TIMEOUT = 30  # seconds to find the scale each time
STABLE_COUNT = 8  # identical packets = stable

CHAR_FFB1 = "0000ffb1-0000-1000-8000-00805f9b34fb"
CHAR_FFB2 = "0000ffb2-0000-1000-8000-00805f9b34fb"
CHAR_FFB3 = "0000ffb3-0000-1000-8000-00805f9b34fb"

USER_HEIGHT_CM = 194
USER_AGE = 34
USER_SEX = 1
USER_UNIT = 0

results = []


def build_user_profile() -> bytes:
    h_hi = (USER_HEIGHT_CM >> 8) & 0xFF
    h_lo = USER_HEIGHT_CM & 0xFF
    body = bytes([0xFE, USER_UNIT, 0x00, USER_AGE, h_hi, h_lo, USER_SEX])
    cs = 0
    for b in body:
        cs ^= b
    return body + bytes([cs])


async def do_one_measurement(idx: int) -> dict | None:
    """Connect to scale, capture stable weight, return result."""
    print(f"\n━━ Measurement {idx} ━━━━━━━━━━━━━━━━━━━")
    print("Step on the scale to wake it up…")

    device = await BleakScanner.find_device_by_filter(
        lambda d, _: bool(d.name and d.name.lower().startswith(DEVICE_PREFIX.lower())),
        timeout=SCAN_TIMEOUT,
    )
    if device is None:
        print("Scale not found.")
        return None

    print(f"Found: {device.name} — connecting…")

    last_key = None
    streak = 0
    stable_evt = asyncio.Event()

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
        if streak >= STABLE_COUNT and not stable_evt.is_set():
            hex_key = " ".join(f"{b:02X}" for b in key)
            full = " ".join(f"{b:02X}" for b in data)
            print(f"\n  ✓ STABLE  key={hex_key}")
            print(f"            full={full}")
            stable_evt.set()

    try:
        async with BleakClient(device) as client:
            await client.start_notify(CHAR_FFB2, on_ffb2)

            # Send user profile so scale knows who we are
            try:
                await client.start_notify(CHAR_FFB3, lambda *_: None)
                await asyncio.sleep(0.5)
                await client.write_gatt_char(
                    CHAR_FFB1, build_user_profile(), response=False
                )
            except Exception:
                pass

            print("Connected — stand still…")

            # Wait for stable reading or connection drop
            try:
                await asyncio.wait_for(stable_evt.wait(), timeout=60)
            except asyncio.TimeoutError:
                print("  Timed out.")
                return None

            await asyncio.sleep(1.5)
            weight_str = input("  Display shows (kg): ").strip()
            try:
                kg = float(weight_str)
            except ValueError:
                kg = None

            result = {"idx": idx, "key": bytes(last_key), "kg": kg}
            print("  Saved. Step off — scale will power down.")
            return result

    except Exception:
        # Connection likely dropped when scale powered off — that's fine
        if stable_evt.is_set() and last_key:
            weight_str = input("  (disconnected) Display showed (kg): ").strip()
            try:
                kg = float(weight_str)
            except ValueError:
                kg = None
            return {"idx": idx, "key": bytes(last_key), "kg": kg}
        return None


def report() -> None:
    print("\n\n══ Results ══════════════════════════════")
    print(f"{'#':<4} {'kg':<10} {'bytes 7-10':<24} raw")
    print("─" * 60)
    for r in results:
        h = " ".join(f"{b:02X}" for b in r["key"])
        print(f"{r['idx']:<4} {str(r['kg']):<10} {h:<24} {list(r['key'])}")

    valid = [
        (int.from_bytes(r["key"], "big"), r["kg"])
        for r in results
        if r["key"] and r["kg"] is not None
    ]

    if len(valid) < 2:
        print("\nNeed at least 2 readings.")
        return

    print("\n══ Formula fit ══════════════════════════")
    xs = [v[0] for v in valid]
    ys = [v[1] for v in valid]
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    den = n * sx2 - sx * sx
    if den == 0:
        print("All values identical — can't fit.")
        return
    slope = (n * sxy - sx * sy) / den
    intercept = (sy - slope * sx) / n
    print(f"\n  weight_kg = {slope:.10f} × raw32 + {intercept:.6f}")
    print("\n  Verification:")
    for x, y in valid:
        pred = slope * x + intercept
        print(f"    raw={x}  pred={pred:.2f}  actual={y}  err={pred - y:+.3f}")


async def main() -> None:
    idx = 1
    try:
        while True:
            result = await do_one_measurement(idx)
            if result:
                results.append(result)
                idx += 1
            again = input("\nAnother? (y/n): ").strip().lower()
            if again != "y":
                break
    except KeyboardInterrupt:
        pass
    report()


if __name__ == "__main__":
    asyncio.run(main())
