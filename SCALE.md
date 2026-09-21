# Smart Scale Integration

Fitman reads body composition directly from the **e.volve Bluetooth smart scale** (sold with the Fitdays app, EAN 8720828067765), without sending data to any cloud service. The scale is an **iCOMON FG2305ULB** (firmware A1.1.14).

## ⚠️ Medical disclaimer

**The developers of Fitman are not medical professionals.** All body composition metrics beyond raw weight (body fat %, muscle mass, body water, BMR, visceral fat, WHR estimate, etc.) are estimates derived from bioelectrical impedance analysis (BIA) and published or vendor formulas. They are not clinically validated measurements and **must not be used for medical diagnosis, treatment decisions, or as a substitute for professional medical advice.** Always consult a qualified healthcare professional.

---

## Enabling it

The integration is **opt-in**: set `SCALE_ENABLED=true` in `.env` (#326). Off, which is the default, Fitman offers manual weight entry only, the scale endpoints return 404 and no Weigh-in button appears. `GET /api/features` tells the frontend which it is.

**Weighing in.** On the Progress page, the Body weight card shows **Weigh in** next to *Log measurement*. Tap it, pick the `e.volve` scale in the browser's device chooser, then step on barefoot and hold the handle. Live weight shows while you stand; when the scale beeps, the result is stored and appears in the chart. This needs Web Bluetooth and HTTPS (README, step 5): Chrome on Android, or **Bluefy** on iPhone. Elsewhere the card says so and names Bluefy.

## How it works

Step on barefoot and grip the handle bar. The scale passes a small current at two frequencies (20 kHz and 100 kHz) between its hand and foot electrodes and measures the impedance of each limb. That is multi-frequency segmental BIA.

**The scale computes body fat itself**, from the profile (height, age, sex) it is sent at the start of each connection. Fitman sends the logged-in user's own profile, so each person on the same scale gets their own result. Fitman stores the weight, the scale's body fat and the limb impedances, and derives the other metrics in `backend/formulas.py`.

**The exchange (#323).** Each request to `POST /api/scale/exchange` carries the frames the scale sent (hex), the handshake state the phone keeps (`phone_seq`, `sequence_sent`) and the phone's UTC offset. The response carries the frames to write to FFB1, the updated state, and a stored measurement once a result arrives. The backend stays stateless. Each user gets a `scale_user_id` (4 random bytes) on their first weigh-in; the scale keeps history per id and tags results with it. A result is stored only if it carries the logged-in user's id. `A5` stored weigh-ins are acknowledged but not stored, since they carry no user id. Height, birth year and sex (male or female) must be set in the profile; there are no fallback values.

Bluetooth is short-range, so something near the scale has to talk to it. Fitman's plan (#59) is the phone: the web app relays frames between the scale and the backend over Web Bluetooth (#322). On iPhone, that needs the Bluefy browser (Safari has no Web Bluetooth) and HTTPS (#321). The backend owns the protocol (`backend/scale/`, #319) and the exchange (#323).

## BLE protocol

Decoded from the Fitdays app's own Bluetooth traffic and verified by replaying it with other profiles and user ids (#320).

**Device:** name prefix `e.volve` · **Service:** `0000FFB0-0000-1000-8000-00805F9B34FB`

| Characteristic | Properties | Use |
|---|---|---|
| FFB1 | write (with response) | Framed messages from the phone |
| FFB2 | notify | Live weight while standing (12 bytes) |
| FFB3 | indicate | Framed messages from the scale |
| FFB4 | write without response | Name image for the display (#324) |

### Framing

Every message on FFB1 and FFB3:

```
[seq u16 LE][len u16 LE = 1 + payload length][type][payload][check]
check = sum(type + payload) & 0x1F
```

| Type | From | Meaning |
|---|---|---|
| `AA` | scale | Hello, on connect |
| `B0` | phone | Acknowledge a scale message by its seq (hello, result, stored record) |
| `BE` | phone | User record, and sets the scale's clock: Unix time u32 BE, UTC offset in minutes i16 BE, `01`, height, weight u16 BE ÷ 100, sex\|age, previous weight, target weight, flag, user id, tail. Sent first for a built-in guest, then for the user. |
| `BF` | phone | **The profile body fat is computed from:** `01 01 [height cm] [last weight u16 BE ÷ 100] [sex\|age] 00 00 00 00 0F [user id, 4 B] 01 01`. sex\|age = `0x80` if male, OR'd with the age. |
| `A0` | scale | Acknowledge a phone message by its seq |
| `BD` | phone | `09`. The scale answers `A8` with the name image id it holds for the user. |
| `BC` | phone | Offer the name image: `01 00`, size u32 BE (twice), 16-bit byte sum, user id, image id. The scale answers `AD`: `01 00 20 00 95` asks for it (0x95 = 149-byte chunks), `01 04 …` means it already holds that image id. |
| `A7` | scale | **Result** (below). Acknowledge it with `B0`. |
| `A5` | scale | A weigh-in stored while nothing was connected: same layout as `A7`, no user id. Re-offered every ~10 s until acknowledged. |

The handshake, as Fitdays does it: `AA` → `B0`, `BE` (guest), `BF`, `BE` (user), `BD`, `BC`; after the weigh-in, `A7` → `B0`.

An earlier version of this document described an `FE [unit] 00 [age] [height] [sex] [xor]` profile command. It is not part of this protocol: the scale ignored it and used whatever profile Fitdays had stored.

### Name on the display

Fitman shows each user's display name (or username) on the scale, as Fitdays does (#324). The name is rendered as a 1-bit bitmap in Noto Sans Bold: an 18-byte header `41 00 41 00 01 00 00 00 0C 00 00 00 [w] [w] [h] 00 00 00`, then rows top to bottom, MSB = leftmost pixel, 48 px high. The image id is its byte sum, so the scale only asks for the image again when the name changes. The exchange returns the chunks as `image_chunks`, and the phone writes them to FFB4 without response.

### Result (`A7`, 43 bytes)

| Bytes | Content |
|---|---|
| 5–8 | Timestamp: the scale's clock, Unix u32 BE |
| 10 | Status; bit 0 is weight bit 16 |
| 11–12 | Weight in grams, low 16 bits (with the status bit: 65.536 kg and up) |
| 16–23 | Four impedances at 20 kHz, int16 LE ÷ 10 → Ω |
| 26–33 | Four impedances at 100 kHz, int16 LE ÷ 10 → Ω |
| 24–25, 34 | Trunk impedance? **Unresolved** (#320) |
| 35–38 | User id the result was computed for |
| 40–41 | **Body fat %**, uint16 BE ÷ 10, computed by the scale from the `BF` profile |

Which limb each impedance position belongs to is not confirmed (#325). Fitman stores them under `ra/la/rl/ll_z20/z100` in packet order.

## Body composition calculations

| Metric | Source |
|---|---|
| Body fat % | **The scale**, from the `BF` profile |
| Fat mass, lean mass, BMR, body water, protein, minerals | `formulas.py`, from weight and body fat |
| Skeletal muscle mass | Janssen et al. (2000); needs trunk impedance, so empty for scale weigh-ins |
| Visceral fat | iCOMON's WLA25 (ported from sacoma-lib, MIT): reproduces Fitdays exactly |
| Trunk fat, trunk muscle | WLA25 with the trunk-impedance terms off: within ~0.6 kg of Fitdays |
| Arm and leg fat and muscle | What's left after the trunk: fat by relative density, lean by each limb's impedance index |

BIA from hand and foot electrodes cannot localise abdominal or visceral fat: the trunk is about half the body's mass but a small share of the measured impedance. Every such figure, including Fitdays', is an estimate from whole-body fat and lean mass.
