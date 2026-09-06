# Data Model: viaim RecDot as a Native Omi Device

Entities are described by what they represent and the rules they enforce. Field names are
indicative; the Dart shapes follow Omi's existing conventions (`BtDevice`, `DeviceLocator`,
`Wal`, the 001 import job).

---

## RecDotDevice

One logical device made of two buds and a case, surfaced to Omi as a `BtDevice` of type
`viaimRecDot`.

| Field | Meaning | Rules |
|---|---|---|
| `id` | Omi device id | iOS: the accessory's serial or connection id; Android: the classic MAC. Stable across reconnects |
| `locator` | How to reach it | `TransportKind.externalAccessory` (iOS) or `bluetoothClassic` (Android), appended enum values |
| `productId` | 8 = RecDot, 9 = RecDot 2 | From the serial prefix after connect (`A92`/`A96`), or the BLE advert if seen |
| `serials` | Left, right, case | 14-char ASCII from `0x550B` |
| `firmwareVersion` | Dotted string | From `0x5500`; shown, not gated |
| `battery` | Left, right, case: percent or absent; charging flag each | From `0x5505` at connect and `0x5504` pushes; absent parts shown as absent, never 0 |
| `masterSide` | Which bud currently owns the phone link | From `0x5504` attr 4; FlashRecord targets this side |

## LinkSession

The open byte channel to the buds, owned by the transport.

| Field | Meaning | Rules |
|---|---|---|
| `state` | disconnected → connecting → connected → disconnecting | Mirrors `DeviceTransportState` |
| `framer` | Byte-stream reassembler | Resyncs on `0x55`/`0x56`; discards until a sync byte; a total length of exactly 256 is never produced |
| `pendingCommand` | At most one outstanding request per opcode | No transaction ids on the wire (protocol.md §3): a second identical request waits for the first's ACK or timeout (12 s, matching the vendor) |
| `lastByteAt` | Liveness | Silence beyond 3 s while a stream is expected triggers the reopen watchdog |

**Connect sequence**: transport open → `0x5101` bond check with code 0 → `0x550B` serial →
`0x5500` version → `0x5505` battery → `0x5534` seamless-record on → `0x5410` VoIP declared →
state `connected`. Any ACK status ≠ 0 surfaces as a user-readable error naming the step.

## CaptureSession

One capture, live or replayed from a stored recording, feeding two channel streams into
transcription with attribution.

| Field | Meaning | Rules |
|---|---|---|
| `origin` | `liveCall`, `liveRoom`, `storedRecording` | Decides pacing: live is unpaced; stored is paced by the import pump |
| `mode` | `onDevice` or `cloud` | Resolved from the user's existing transcription config at start; fixed for the session |
| `channels` | `user` (mic) and `remote` (far end); `liveRoom` has `user` only | Each channel is an `AudioSource` producing 320-byte PCM16 frames at 16 kHz |
| `sampleRateMode` | 8 kHz or 16 kHz G.722 | From `0x500F`/`0x5010` per call; each channel's decoder is reset when it changes |
| `state` | idle → starting → capturing → paused → ending → closed | `paused` sends `0x500C` with the pause flag and discards nothing already captured |
| `gaps` | Link losses during capture | Each is stored as a (start, end) and rendered in the conversation |
| `conversationId` | The conversation being built | Created by Omi's existing processing, unchanged |

**On-device mode**: two `PurePollingSocket`s; channel `user` stamps `speakerId 0, isUser true`,
channel `remote` stamps `speakerId 1, isUser false`; segments are merged by `start`.
**Cloud mode**: frames prefixed `0x01`/`0x02`, one socket with `channels=2`.

**Invariant**: a `CaptureSession` never starts while another live Omi capture is running on the
phone, and a `storedRecording` session never starts while a call is active (FR-014, FR-021).

## ChannelStream

One side's audio inside a `CaptureSession`.

| Field | Meaning | Rules |
|---|---|---|
| `role` | `user` or `remote` | Fixed at creation |
| `decoder` | G.722 state for this channel | One instance per channel; never shared |
| `frames` | 320-byte PCM16 frames with wrapping sync keys | Same obligations `PhoneMicSource` is tested against (`test/unit/audio_source_test.dart`) |
| `wal` | Per-channel WAL stream | Two files, never interleaved (research F-6) |

## StoredRecording

One recording on the buds, as reported by `0x5A37`.

| Field | Meaning | Rules |
|---|---|---|
| `side` | Which bud holds it | Transfer requires that bud to be master; otherwise a master switch is requested first |
| `index` | The bud's index for it | With `side` and the bud serial, forms the transfer identity |
| `lengthBytes` | G.722 bytes on the bud | Used for resume arithmetic and the completion check |
| `sampleRateMode` | 8 or 16 kHz | Decides decoder mode and bytes-per-second |
| `kind` | `call` (two-way) or `room` (single) | Two-way clips produce two channels |
| `recordedAt` | Unix seconds from the bud | The recording's true time; carried to the import job |
| `isProtected` | Passcode set | Listed, reported to the user, skipped |

## TransferJob

Moving one `StoredRecording` to the phone and turning it into a conversation.

| Field | Meaning | Rules |
|---|---|---|
| `identity` | (bud serial, side, index, recordedAt) | Idempotency key: a job with this identity that already reached `imported` is never re-run |
| `state` | see below | Persisted before every transition that talks to the bud |
| `offsetBytes` | Bytes received so far | Resume point; recomputed from the scratch file on restart |
| `scratchFiles` | Decoded PCM per channel | Deleted after `imported` or on `abandoned` |
| `verification` | Bud-reported length vs received | Tolerance `max(len/100, 2 s)` capped at 10 s, matching the vendor; failure → `mismatch`, user told |
| `importJobId` | The 001 import job created from the scratch files | Its completion is what authorises deletion |

**States**: `listed` → `downloading` → `received` → `verified` → `importing` → `imported` →
`deletingOnBud` → `done`; side exits `interrupted` (resumable from `downloading`), `mismatch`,
`protected`, `abandoned` (after 3 failed deletes, matching the vendor).

**Invariant, enforced in persistence**: the transition to `deletingOnBud` is only legal from
`imported`, and `imported` is only set by the import job's durable-persist callback. Nothing in
the UI can issue `0x5A38`.

**Invariant**: `downloading` is refused while a `CaptureSession` of origin `liveCall` or
`liveRoom` exists, and an incoming call (`0x5A3B` reason 2 or the platform observer) moves a
`downloading` job to `interrupted` immediately.
