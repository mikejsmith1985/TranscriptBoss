# viaim RecDot — observed Bluetooth protocol

**Purpose**: the facts an Omi connector needs, recovered by reading the viaim Android app
(`tws.vision.viaim.headset` 2.3.0, build 1170, decompiled with jadx 1.5.6 on 2026-09-06).
Observed behaviour only. No vendor code is reproduced here. Class references point at the
decompiled tree so any claim can be re-checked; obfuscated package names (`p025b8`, `p085f8`,
`p165kd`, …) are jadx's, not the vendor's.

**Status**: static analysis of the Android app. Nothing below has been confirmed against a live
RecDot yet, and the **iOS transport is unresolved** (§2.3). Dynamic confirmation is Phase A step 2.

---

## 1. What the RecDot is

- The app is iFLYTEK's international "viaim" brand. It serves several headset families;
  **RecDot is the overseas branding of "iFLYBUDS Pro 2"** and **RecDot 2 of "Pro 3"**.
- Product table (`com/vision/bluetooth/utils/Constants`, `device/DevicePro2`, `DevicePro3`):

| Product id | Class | Serial prefixes | Name |
|---|---|---|---|
| 8 | `DevicePro2` | `A08` (CN), `A92` (overseas) | viaim RecDot |
| 9 | `DevicePro3` | `A09`, `A96` | viaim RecDot 2 |
| 6908 | `DeviceAir2` | `E08`, `E97` | viaim OpenNote |

- Chip family: **BES (Bestechnic)**. `isBES()` is true for every model except the two legacy
  Qualcomm ones (Buds, Lite). Firmware update uses the vendored BES OTA SDK over its own
  RFCOMM UUID `66666666-6666-6666-6666-666666666666`. Internal asset codename for product 8
  is `ares`.

## 2. Transport

### 2.1 What the Android app does

| Link | Used for | Detail |
|---|---|---|
| BLE advertising | **Discovery only** | Unfiltered scan; keep adverts with manufacturer-data (AD type 0xFF) ≥ 21 bytes and RSSI ≥ −70 dBm; decode §2.2. No GATT connection is ever made |
| Classic RFCOMM (SPP) | **All commands and all earbud audio** | `createInsecureRfcommSocketToServiceRecord` on `00001101-0000-1000-8000-00805F9B34FB` (standard SPP); fallback UUIDs `544f5241-5453-7070-6153-445542594c46` and `…-7070-7353-…` (ASCII "…FLYBUDSapp STAROT"); 7 s connect timeout, 21 s overall watchdog; 1024-byte reads |
| HFP / SCO | **Never opened by the app** | No `startBluetoothSco`, no `VOICE_COMMUNICATION` capture. The call's audio path is untouched |
| BLE GATT (`GAIAGATTBLEService`) | Present as a stub | No characteristic UUIDs used, no MTU request, no caller passes the BLE transport selector |

The SPP channel is a third RFCOMM channel on the same ACL link as the A2DP/HFP profiles; the
app requires the buds to already be bonded and connected as a headset before it opens it.

### 2.2 BLE advertisement, 21-byte manufacturer payload

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | product id low byte (RecDot `0x08`, RecDot 2 `0x09`) |
| 1 | 1 | product prefix letter, ASCII, or 0 (OpenNote: `'E'` → id 6908) |
| 2 | 1 | unused |
| 3 | 1 | left bud battery: bit 7 charging, bits 0–6 percent (`0xFF` absent) |
| 4 | 1 | right bud battery, same layout |
| 5 | 1 | case battery, same layout |
| 6–7 | 2 | random code, big-endian |
| 8–13 | 6 | **left bud BR/EDR MAC** |
| 14–19 | 6 | **right bud BR/EDR MAC** |
| 20 | 1 | feature: 0 = normal (GAIA), 1 = pairing, 2 = upgrade |

Final id = `(prefix > '0' ? prefix × 100 : 0) + byte0`. Bytes 0–1 sit where a Bluetooth SIG
company id normally goes, so a generic scanner will mis-read the company id. Secondary
heuristics in the app: classic address OUI `20:FF:…` or `0C:1B:…`, or a classic name
containing `iflybuds` / `viaim`.

**Observed on the user's iPhone (nRF Connect, 2026-09-06)**: the RecDot advertises exactly
this blob, `08 08 08 00 FF FF 30 41 20 FF 36 E9 2A 64 20 FF 36 E9 08 E0 00`, which the
reference codec decodes to product 8 with bud addresses `20:FF:36:E9:2A:64` /
`20:FF:36:E9:08:E0`. The scanner shows it **unnamed**, labels the first two bytes as a
company id, lists Battery Service `0x180F` in the advert, and offers **no Connect button**:
the advertisement is non-connectable. That is consistent with BLE being discovery-only.

### 2.3 Consequence for iOS — UNRESOLVED, MFi now the leading hypothesis

A third-party iOS app cannot open RFCOMM, and the BLE advert is non-connectable. viaim
markets the sibling OpenNote as "MFi certified", which for a Bluetooth accessory means iAP2
over the Classic link, i.e. an External Accessory session. The viaim iOS app therefore uses
one of:

| Possibility | How Omi would follow | How to confirm |
|---|---|---|
| A firmware BLE GATT service the Android app never uses (BES parts commonly expose one; the stub keeps CSR GAIA UUIDs `00001100/1101/1102/1103-d102-11e1-9b23-00025b00a5a5`) | CoreBluetooth central, write to the command characteristic, notify on response/data — the normal Omi connector shape | A BLE scanner app on the iPhone (nRF Connect / LightBlue) connected to the RecDot lists its GATT services |
| MFi External Accessory session (iAP2 over Classic) | `ExternalAccessory` framework with the accessory's protocol string in Info.plist; works on TestFlight, App Store needs the vendor's MFi allow-listing | The viaim iOS app's `Info.plist` → `UISupportedExternalAccessoryProtocols`; or the sniffer shows no LE data traffic during a call recording |
| BLE L2CAP connection-oriented channel | CoreBluetooth `openL2CAPChannel(psm)` | GATT would expose a PSM characteristic; sniffer shows L2CAP CoC |

Throughput budget either way: G.722 is 64 kbit/s per channel, so a two-channel 16 kHz call is
128 kbit/s (16 KB/s); the 8 kHz mode halves it. Feasible on a 2M-PHY BLE link with DLE, but must
be measured on the iPhone.

## 3. Packet framing ("STAROT" GAIA, vendor id 15)

Two framings exist, chosen per product. **RecDot uses v2.** v1 is only for products 1 and 2.

| Sync byte | Framing | Layout |
|---|---|---|
| `0xFF` | v1 (legacy Qualcomm models) | `FF 01 flags len(1) vendor(2 BE = 000F) command(2 BE) payload…` (+1 checksum byte if `flags & 1`, never set) |
| `0x55` | **v2, total ≤ 256** | `55 len(1) command(2 BE) payload…` where len = total frame length |
| `0x56` | **v2, total > 256** | `56 (total − 256)(1) command(2 BE) payload…` |

- Maximum payload 508 bytes. No vendor field, no sequence number, no checksum, no encryption.
- Edge case in the vendor encoder: a frame of exactly 256 bytes writes length `0x00`, which the
  framer cannot resync on. Keep total frames ≤ 255 or ≥ 257.
- `command & 0x7FFF` = opcode; `command & 0x8000` = **ACK**. In an ACK, payload[0] is a status
  byte and real data starts at payload[1]. Status codes: 0 success, 1 not supported, 2 not
  authenticated, 3 insufficient resources, 4 authenticating, 5 invalid parameter,
  6 incorrect state, 7 in progress, 8 offline.
- Most payloads are TLV groups: `[len][attr][value…]` where `len = valueLen + 1` (counts the
  attr byte, not itself); decoder advances by `len + 1`. Multi-byte values are big-endian when
  read, but the FlashRecord download request writes its integers **little-endian**.
- Opcodes are grouped `0x5X00 | sub` by feature area: `0x50xx` dialog/call, `0x51xx` bond,
  `0x52xx` mic record (legacy), `0x54xx` control, `0x55xx` device info, `0x56xx` debug,
  `0x57xx`/`0x58xx` OTA, `0x59xx` translator bulk transfer, `0x5Axx` device control incl.
  FlashRecord and far-field record.
- Request/response matching is by opcode only: no transaction id. Two concurrent identical
  requests cross-talk. The app serialises sends on one thread at ~50 ms per packet.

## 4. Connect sequence (as the Android app performs it)

1. BLE scan → decode §2.2 → take the bud MACs and product id.
2. Match against bonded-and-connected classic headsets; if absent and the advert says
   "pairing", run classic inquiry and bond.
3. Select framing v2 for product 8/9, open RFCOMM on the SPP UUID (§2.1).
4. Immediately after the byte stream opens, the app treats the link as ready.
5. **Bond-code check**: send `0x5101 CHECK_BOND_CODE` with a 4-byte big-endian code of **0**.
   Wire bytes in v2 framing: `55 08 51 01 00 00 00 00`. 12 s timeout, ≤ 2 retries. Only the
   legacy Buds model uses a real random code via `0x5100 SET_BOND_CODE`.
6. On ACK status 0: `0x550B GET_SN` (wire `55 04 55 0B`); the 14-byte ASCII serial prefix
   (`A92`/`A96`) confirms RecDot branding. Then the device is "connected".
7. Optional: `0x5500 GET_VERSION` with TLV `02 01 07` (wire `55 07 55 00 02 01 07`);
   reply carries an 8-byte hex string, product code in hex chars 2–4, dotted version after.

## 5. Live audio during a call — the both-sides path

### 5.1 Commands

| Action | Opcode | Payload |
|---|---|---|
| Start streaming call audio | `0x500B` DIALOG_START_TRANS_AUDIO | TLV attr 2 = `[isResume]` |
| Stop streaming | `0x500C` DIALOG_STOP_TRANS_AUDIO | TLV attr 2 = `[isPause]` |
| Restart after stall / reconnect | `0x500B` again, no payload | the app's recovery path |
| **Audio data, bud → phone** | **`0x5007` DIALOG_AUDIO_DATA** | §5.2 |
| Call attributes / active | `0x500F` DIALOG_ATTR, `0x5010` DIALOG_ACTIVE | carries sample-rate type 8 K / 16 K |
| Force 8 kHz | `0x5409` SET_8K / `0x540E` GET_8K | renegotiate = stop → set → start |
| Declare a VoIP call (Teams, Zoom) | `0x5410` SET_CALL_TYPE | attr 1 = 1 |
| Bud asks to start call record (unsolicited) | `0x5013` → app replies `0x5015` | attr 1 = reply code |
| Seamless / "Safe Record" flag on the bud | `0x5533` get / `0x5534` set | attr 1 = 0/1 |
| Mute | `0x5406` / `0x5407` / `0x5408` | |
| Packet-loss report | `0x5012` | defined, not dispatched in this build |

No keep-alive exists on the audio stream. The app re-sends start on reconnect or on an
A2DP/HFP state change.

### 5.2 `0x5007` payload layout

```
[framing][B0][ speaker block ][ mic block ]
```
- `B0 & 0x0F` is a channel bitmask: bit 0 (1) = **Speaker = far end**, bit 1 (2) = **Mic = near
  end**, bit 2 (4) = VPU bone-conduction mic, bit 4 (16) = TalkMinusVpu. Upper nibble unused.
- When both Speaker and Mic bits are set, the remaining bytes are split into **two equal
  halves**, speaker first. No per-block length, no sequence number.
- Each half is raw **G.722**: 40-byte frames in 8 kHz mode, 80-byte frames in 16 kHz mode.
  8 kHz output is resampled to 16 kHz in native code. Everything lands as 16 kHz / 16-bit /
  mono per channel.

**Plan question Q5 answered**: the call is delivered as **two independent channels**. The
vendor app decodes each with its own G.722 instance, writes `_Speaker` and `_Mic` WAV files,
and runs two speech recognisers. Omi can attribute speakers exactly.

### 5.3 Other live modes

| Mode | Opcodes | Codec |
|---|---|---|
| Far-field mic record on BES models (RecDot) | `0x5A75` start (TLV attr 1), `0x5A76` stop, `0x5A77` data | **mSBC**: payload `1 + N×57`, 57-byte frames → 240 B PCM, frames alternate mic A / mic B |
| Mic record, legacy Qualcomm models | `0x5205` / `0x5206`, data `0x5202` | G.722 |
| Media / caption record | `0x540F` start, `0x5411` register, data `0x5413` | G.722, same channel-bitmask layout as `0x5007` |
| Call-translation audio | data `0x5925` | fixed 120-byte groups = 40 B Mic + 40 B VPU + 40 B Speaker |
| In-person "on-site" record | none | the vendor app uses the **phone's own microphone**, not the buds |

### 5.4 Why Teams keeps working

Earbud audio never touches SCO; it rides the data channel as a parallel link. The app never
calls `startBluetoothSco`. Live recording and FlashRecord download are mutually exclusive with
each other and with an active call's download, so the data link never carries a bulk transfer
during a call. Omi inherits all of this by using the same channel.

## 6. FlashRecord (recordings stored on the buds)

Feature area "OfflineControl"; vendor UI strings call it 闪录.

### 6.1 Command set

| Opcode | Name | Direction | Payload (TLV attrs) |
|---|---|---|---|
| `0x5A99` | OFFLINE_START | app → bud | mapped, unused by the app |
| `0x5A31` | OFFLINE_MSG | bud → app | 1 headset, 2 state, 3 length, 4 frames, 5 free, 6 phone, 8 type, 9 timestamp |
| `0x5A34` | NOTIFY_STOP | bud → app | 1 headset, 2 stop reason |
| `0x5A35` | OFFLINE_CONTROL | app → bud | single attr, no value: 1 = STOP, 2 = GET_STATE |
| `0x5A36` | GET_RECORD_INFO | app → bud | empty; reply 1 headset, 2 free, 3 count, 4 total, 5 flashId (3 bytes) |
| `0x5A37` | GET_RECORD_LIST | app → bud | req attr 1 = side (1 left, 0 right); **one reply packet per file**: 1 side, 2 index, 3 phone (ASCII), 4 length, 5 sample rate (1 = 8 K else 16 K), 6 type (0 CALL, 1 MIC_FAR), 7 unix timestamp; attr **15 = end of list** |
| `0x5A38` | OFFLINE_DELETE | app → bud | 1 side, 2 index (int32 **LE**), optional 3 = clear all |
| `0x5A39` | GET_RECORD | app → bud | **start / resume**: 1 side, 2 index LE32, 3 offset LE32, 4 length LE32, optional 5 = password (ASCII). **Cancel** = single attr `0xFF`, no value. Reply: 1 side, 2 index, 3 offset, 15 error |
| `0x5A3A` | OFFLINE_UPLOAD | bud → app | bulk audio, §6.2 |
| `0x5A3B` | GET_RECORD_ERROR | bud → app | 1 = master/slave switch, 2 = incoming call |
| `0x5A3D` | FLASH_PASSWORD_CTRL | app → bud | 1 side, then 2 query / 3 set / 4 check / 5 delete |

`GET_RECORD` ack errors: 1 wrong ear (switch master), 4 another phone is downloading,
5 flash recording in progress, 6 password failed, 7 recording started on the other device.

### 6.2 `0x5A3A` chunk layout

```
[ offset: 3 bytes big-endian, byte offset into the file ][ channel: 1 byte ][ payload … ]
```
- channel `3` → single stream, tagged Speaker.
- channel `4` → **two-way flash**: payload is 40-byte frames alternating Speaker / Mic.
- channel `255` → **end of file**, no data.
- The bud free-runs; the app **never acks chunks**. It checks `prevOffset + prevLen == offset`
  and logs a gap; the only flow control is the cancel form of `0x5A39`. Three seconds of
  silence after the `GET_RECORD` ack is treated as failure.

### 6.3 Format, resume, limits

- On-bud codec is raw **G.722**, 8 or 16 kHz per record.
- Resume is offset-driven: PCM bytes already saved → G.722 bytes (`/16`, halved for 8 kHz,
  doubled for two-way); if the offset exceeds the reported length, restart from 0.
- Completed duration is cross-checked against the bud-reported length (tolerance
  `max(len/100, 2 s)`, capped at 10 s) before the recording is accepted. Delete is retried
  up to 3 times.
- **Refused during a call, a live recording, or an active flash recording**; if a call arrives
  mid-transfer the bud sends `0x5A3B` reason 2 and the app aborts.
- The target bud must be the **master**; otherwise the app issues a master switch, waits for
  the change event, re-reads battery, waits 1–2 s, retries.

## 7. Device info and battery

| Opcode | Name | Notes |
|---|---|---|
| `0x5500` GET_VERSION | TLV `1 = 0x07` | reply attrs 1/2/4 = 8-byte hex version strings |
| `0x550B` GET_SN | empty | reply attrs 1–4 = 14-byte ASCII serials (left / right / case) |
| `0x551F` GET_MAC | empty | reply 1 = left MAC, 2 = right MAC |
| `0x5505` GET_POWER_POSITION_CONNECTION / `0x5504` notify | | attr 1 left, 2 right, 3 case: `0xFF` absent, bit 7 charging, bits 0–6 percent; attr 4 position bitfield; attr 5 connection bitfield |
| `0x5520` / `0x5521` | get / set name | TLV 1 = UTF-8 |
| `0x5A71` FIND_HEADSET | attr 1 start / 2 stop, value 1 left / 0 right | |

Battery also arrives for free in every BLE advert (§2.2), which Omi can use before connecting.

## 8. Translator bulk-transfer layer (app → bud, not needed for capture)

`0x59xx` commands carry a windowed, NACK-bitmap ARQ layer with a 2-byte sub-header
(frame index; session id / data type / phase flags) and negotiated frame size (default 80 B
payload, window 4). Recorded for completeness; Omi's capture and FlashRecord paths do not use it.

## 9. What Omi needs from this

| Omi piece | Fed by |
|---|---|
| Live both-sides capture during Teams on the iPhone | `0x500B` start, `0x5007` two-channel G.722, `0x500C` stop |
| Speaker attribution | Speaker vs Mic halves of each `0x5007` packet |
| Phone-less capture and later sync | `0x5A37` list → `0x5A39` download → `0x5A3A` chunks → persist → `0x5A38` delete |
| Battery in the device list | BLE advert bytes 3–5, or `0x5505` |
| Identity | advert product id 8/9 + bud MACs; serial prefix `A92`/`A96` after connect |
| Codec | G.722 decoder (Core Audio has none; a small pure-Dart or C decoder is needed), optional mSBC |
| Transport on iOS | **unresolved, §2.3** — decides the whole iOS connector class |

## 10. Open items

1. **iOS transport** (§2.3). Fastest check: a BLE scanner app on the iPhone connected to the
   RecDot, listing its GATT services. Definitive check: the viaim iOS app's `Info.plist`
   (`UISupportedExternalAccessoryProtocols`, `UIBackgroundModes`) and its GATT UUID strings.
2. Sustained BLE throughput on the iPhone at 128 kbit/s; whether to prefer `SET_8K`.
3. Whether the bud accepts `0x500B` from a second host while the Viaim app is not connected
   (expected yes: bond code 0, no session state observed).
4. Golden fixtures: capture one `0x5007` burst and one FlashRecord download for hermetic tests.
