# Research: viaim RecDot as a Native Omi Device

**Date**: 2026-09-06 · **Method**: direct source analysis of `omi-fork/app` and `omi-fork/backend`
(pinned per `specs/001-omi-audio-import/research.md`), the vendor protocol notes in
[protocol.md](./protocol.md), and the vendor's iOS bundle (`Info.plist` only; the binary is
encrypted). Every file reference below was read this session.

---

## Part 1 — What Omi already provides (Article VII recon)

### F-1 The device seam is designed for this

Third-party wearables are one enum value plus one connector: `DeviceType` at
`lib/backend/schema/bt_device/bt_device.dart:187`, seven exhaustive switches the compiler will
name, `DeviceConnectionFactory.create` at `lib/services/devices/connectors/device_connection.dart:125`,
and a `DeviceTransport` interface (`lib/services/devices/transports/device_transport.dart:5-26`)
that non-BLE devices satisfy with **synthetic characteristic ids**: the Ray-Ban Meta transport
maps `'rayban-meta-audio-service'/'rayban-meta-audio-data'` to a stream and no-ops the GATT
reads/writes (`rayban_meta_transport.dart:216-254`). Swift reaches Dart through Pigeon
(`lib/pigeon_interfaces.dart`, `RayBanMetaFlutterAPI.onAudioFrame` at `:366`).

### F-2 Speaker attribution by channel exists — on the backend

`/v4/listen` accepts `channels=2` (`backend/routers/transcribe.py:173`). Each binary frame
carries a leading channel byte, `0x01` = user, `0x02` = remote (`app/lib/providers/phone_call_provider.dart:358,375`).
The backend opens one speech-to-text socket per channel and stamps `is_user` and `speaker`
before segments reach the transcript (`backend/routers/listen/receiver.py:215-237`), skips
diarisation because the channel is ground truth (`backend/routers/listen/runtime.py:616-617`),
and the unknown-source fallback mapping is identical to the phone-call one
(`backend/utils/listen_audio.py:33-36`). Constraint: in multi-channel mode only raw PCM16 and
Opus are decodable (`receiver.py:130-137`).

The normal capture socket builder has no `channels` parameter
(`lib/services/sockets/transcription_service.dart:98-124`); the phone-call path bypasses it
with its own WebSocket. Adding `channels` to `TranscriptSegmentSocketService.create` is the
one change that brings ordinary capture into that mode.

### F-3 On-device transcription is mono, but segments already carry the labels

`PurePollingSocket` (`lib/services/sockets/pure_polling.dart:34`) buffers one flat byte stream
and calls one `ISttProvider.transcribe`; both on-device providers hard-code `speakerId: 0`
(`on_device_apple_provider.dart:55`, `on_device_whisper_provider.dart:109`). `SttSegment`
already serialises `speaker_id` and `is_user` (`lib/models/stt_result.dart:71-92`), and the UI
keys entirely on `isUser` (`lib/widgets/transcript.dart:816-883`). Two polling sockets, the
second constructed to stamp `speakerId: 1, isUser: false`, therefore produce correctly labelled
segments with no model change. What is missing is a **time-ordered merge**:
`TranscriptSegment.updateSegments` (`transcript_segment.dart:94-117`) merges by id and appends
in arrival order.

### F-4 No G.722 anywhere; the client decodes only Opus

Repo-wide grep for `g722|msbc|sbc` across app, backend and desktop: zero hits. Client codecs:
Opus via `opus_dart`/`opus_flutter` (`app/pubspec.yaml:97-100`). Backend decodes Opus, AAC and
LC3 server-side (`receiver.py:539-550`); PyAV could reach G.722 but nothing in-tree does, and it
would put the audio on the metered cloud path. `BleAudioCodec` has no stereo value
(`bt_device.dart:39-48`); every transcoder's `channels` defaults to 1 and is never set otherwise.

### F-5 Store-and-forward precedents, and which one fits

Limitless flash pages drain into `LocalWalSync` and upload in `WalSyncs` phase 2 — the **cloud**
transcription path (`lib/services/wals/flash_page_wal_sync.dart`, ack after persistence at
`limitless_connection.dart:934`). That is metered, so it cannot carry twenty hours a week.
Feature 001 built the other precedent: `FileImportSource` (`lib/services/audio_sources/file_import_source.dart`)
plus a paced pump into the **on-device** engine, with content-hash dedupe, progress, interruption
safety and recording-time handling (`specs/001-omi-audio-import/plan.md`, D-1/D-2, C-2). A
downloaded FlashRecord clip, once decoded, is exactly an import.

### F-6 WAL files record a channel *count*, not per-frame tags

`Wal.channel` (`lib/services/wals/wal.dart:96`) is baked into the filename and used as a byte-rate
multiplier (`wal_syncs.dart:200`); every producer writes 1. A two-channel device must keep two
WAL streams, not one interleaved file.

### F-7 Build path

The fork's `personal/ci` branch carries `ios-personal-dogfood` in `codemagic.yaml`: dev flavour,
bundle id `com.mikejsmith.omi`, App Store Connect app `6802326663`, upload to TestFlight with
`submit_to_testflight: false` (no beta review). `app/ios/Runner/Info.plist:168-177` declares
`audio`, `bluetooth-central`, `voip` and others, but **not** `external-accessory`, and no
`UISupportedExternalAccessoryProtocols`. Upstream's Codemagic workflows are separate and untouched.

### F-8 No framework-capabilities ledger

Neither TranscriptBoss nor the fork has a `FRAMEWORK-CAPABILITIES.md`. Flagged; the recon above
is the substitute for this feature.

---

## Part 2 — Vendor and platform facts that shape the design

**Fork pin (T001, 2026-09-06)**: worktree `omi-recdot/` on branch `feature/viaim-recdot` at upstream
`1d91c471cd` ("fix(desktop): shorten settings search placeholder", 2026-09-06). Remotes: `upstream`/`origin` =
BasedHardware/omi (origin push disabled), `fork` = mikejsmith1985/omi.

**Toolchain (T002, 2026-09-06)**: Flutter 3.47.2 stable installed at `%LOCALAPPDATA%lutter`;
`flutter test` runs the hermetic layer locally. Codemagic pins **3.44.5**, so the SDK is switched to
that tag to stop `pubspec.lock`/`analysis_options.yaml` churn from tool migrations; any such churn is
reverted before every fork commit.

**Upstream rules read (T004)**: only INV-UI-1 matches the feature's paths and it opts out of PR-body
citation; upstream `Info.plist` already declares an accessory protocol (Ray-Ban Meta), so appending
`com.vision.voyager` follows precedent; the dead-code ratchet requires every new file reachable from
`main.dart`; the architecture ratchet wants a README in `lib/services/devices/recdot/` (added);
`_legacyDeviceTypeNames` is index-ordered and append-only; Pigeon for `pigeon_interfaces.dart` is
regenerated with `flutter pub run build_runner build`.

- **iOS transport**: External Accessory session on protocol `com.vision.voyager`
  (protocol.md §2.3). iAP2 sessions stay open in the background with the
  `external-accessory` background mode; a suspended app is woken when data arrives. Community
  experience: schedule the session's streams on a dedicated thread's run loop and drain
  `hasBytesAvailable` fully per event, since input streams have been reported to stall when
  serviced on the main run loop.
- **Android transport**: insecure RFCOMM socket on the standard SPP UUID with the two vendor
  UUIDs as fallbacks (protocol.md §2.1); requires the buds to be bonded and connected as a headset.
- **Framing**: v2 STAROT frames, no auth, no checksum; the reference codec and 40 golden tests are
  in `scripts/recdot_wire.py` / `scripts/test_recdot_wire.py`.
- **Call audio**: `0x5007` carries far end and mic as two equal halves of G.722; sample-rate mode
  is negotiated per call (protocol.md §5). No keep-alive; re-send start on reconnect.
- **G.722 reference**: `sippy/libg722`, 283-line public-domain decoder (Steve Underwood 2005,
  CMU 1993, "use … completely unrestricted"). A bit-exact Python build (`pip install G722`) runs on
  the Windows dev machine and can generate golden PCM for any G.722 input, in both the 16 kHz mode
  (0.5 byte per sample) and the 8 kHz mode (1 byte per sample).
- **Call detection on iOS**: the buds push `0x5013 START_CALL_RECORD` when their call link goes
  active if the on-bud "seamless record" flag (`0x5534`) is set; the app answers `0x5015`.
  `CXCallObserver` is the platform-side signal and is already available (the app declares `voip`).

---

## Part 3 — Decisions

### D-1 Transport: External Accessory on iOS, RFCOMM on Android, one Dart connector above both

- **Decision**: `ExternalAccessoryTransport` (Swift, Pigeon `RecDotLinkHostAPI` /
  `RecDotLinkFlutterAPI`) and `RfcommTransport` (Kotlin, same Pigeon surface) implement
  `DeviceTransport` with one synthetic characteristic pair, `viaim-recdot-link` /
  `viaim-recdot-bytes`: `writeCharacteristic` sends raw bytes, `getCharacteristicStream` yields
  raw received bytes. Framing lives in Dart, above the transport.
- **Rationale**: the seam exists (F-1) and the Ray-Ban Meta and Watch transports prove the shape.
  Keeping framing in Dart means the codec is tested hermetically with the Python golden vectors
  and the two native layers are dumb byte pipes, which is all Android parity can honestly claim.
- **Alternatives**: framing in native code (two implementations, untestable here);
  `flutter_bluetooth_serial`-style plugins (Android-only, no iOS EA support); BLE GATT
  (ruled out by observation, protocol.md §2.2).
- **Article VII**: extends Omi's seam; no new abstraction.

### D-2 Attribution: two channels end to end, engine chosen by the user's existing setting

- **Decision**: a `RecDotCaptureSession` owns two channel streams (user mic, far end). In
  **on-device mode** it runs two `PurePollingSocket`s with the second stamped
  `speakerId: 1, isUser: false`, and inserts segments **ordered by start time** (a new
  `mergeByTime` beside `updateSegments`). In **cloud mode** it sends channel-tagged frames with
  `channels=2` through `TranscriptSegmentSocketService.create` extended with a `channels`
  parameter, and the backend attributes (F-2). The mode is whatever `CustomSttConfig` already
  resolves for the user; the RecDot adds no setting.
- **Rationale**: the user's need is the free on-device path; the cloud branch is nearly free
  because the contract exists, and it keeps FR-022 (no behaviour change for any other device).
  Two clean recognisers beat one recogniser on a mix: overlapping speech ("mm-hmm") is common in
  meetings and a mix garbles it.
- **Alternatives**: mix to mono and attribute by per-channel energy per segment (cheaper, but
  overlap is misattributed and the mixed audio transcribes worse); backend-only attribution
  (metered beyond ~20 h/month); no attribution (fails FR-007).
- **Risk**: two concurrent on-device recognisers on the iPhone. Measured on TestFlight; the energy
  fallback is the contingency and is recorded here so it is not re-litigated.

### D-3 G.722 decoding: a pure-Dart port of the public-domain decoder

- **Decision**: `lib/utils/audio/g722_decoder.dart`, ported from `libg722`'s decoder, supporting
  both sample-rate modes and 64 kbit/s only. Golden vectors are generated on the dev machine by
  `scripts/generate_g722_vectors.py` with the bit-exact Python package and committed as fixtures;
  the Dart tests assert bit-exact PCM.
- **Rationale**: Core Audio, MediaCodec and Flutter have no G.722; the decoder is ~250 lines of
  integer arithmetic at 16 kHz, trivial CPU; pure Dart means one implementation for both
  platforms, testable with `flutter test`, no native build step, and no ffmpeg (001 D-1 already
  rejected `ffmpeg_kit_flutter`).
- **Alternatives**: `dart:ffi` to the C source (two native builds, no local toolchain to check
  them); decode on the backend via PyAV (audio leaves the device, cloud path); ask the buds for
  Opus (they do not offer it).
- **Article VII**: documented gap; justification recorded at the file header. Attribution to
  Steve Underwood / CMU carried in the header per the public-domain notice's request.

### D-4 FlashRecord: download, decode, then run it as an import

- **Decision**: `RecDotFlashSync` lists (`0x5A37`), downloads (`0x5A39`/`0x5A3A`) into a per-
  recording scratch file of decoded PCM per channel, verifies length against the bud's report,
  then hands the files to feature 001's import job with the recording's true time and a content
  identity derived from (bud serial, index, timestamp). Deletion on the bud (`0x5A38`) is issued
  only after the import job has durably persisted the audio, enforced in the sync's state
  machine, not the UI. Two-way clips run through the same two-channel session as live calls
  (D-2), paced by the import pump.
- **Rationale**: F-5 — the import path already solves pacing, dedupe, interruption safety,
  progress, notifications and the recording-time limitation on the on-device engine. Reusing it
  keeps the cloud WAL path untouched and gives FR-015/16/17 for free.
- **Alternatives**: Limitless-style WAL drain (cloud transcription, metered); a bespoke transfer
  pipeline (duplicates 001).
- **Scheduling**: a new `WalSyncs`-style phase is *not* added; the sync is triggered by the
  connection's "connected and idle" event and refuses to run during a call or live capture
  (protocol.md §6.3 matches the buds' own refusal).

### D-5 Discovery and identity: from the accessory list, not a scan

- **Decision**: `DeviceType.viaimRecDot`; a `ViaimRecDotDiscoverer` that on iOS enumerates
  `EAAccessoryManager.connectedAccessories` filtered on `com.vision.voyager`, and on Android the
  bonded-and-connected headsets whose name contains `viaim`/`iflybuds` or whose address prefix is
  `20:FF`; a new `TransportKind.externalAccessory` and `TransportKind.bluetoothClassic` appended to
  the enum (never reordered — `fromJson` is index-based). Identity confirmed after connect by the
  serial prefix (`0x550B`); battery from `0x5505` and the `0x5504` push.
- **Rationale**: the buds are already paired as a headset; a BLE scan adds nothing the accessory
  list does not already know, and the BLE advert is optional battery-before-connect only.

### D-6 Call start and stop: bud push first, platform observer second

- **Decision**: on connect, set the on-bud seamless-record flag (`0x5534`) and declare VoIP calls
  (`0x5410`); treat the bud's `0x5013` push as the primary "call started" signal (reply `0x5015`,
  send `0x500B`); use `CXCallObserver` (iOS) / telephony state (Android) as the fallback and as the
  "call ended" signal (`0x500C`). A user pause in Omi suppresses `0x500B` until resumed.
- **Rationale**: the bud knows exactly when its call link is active, including VoIP calls the
  platform observer may not expose uniformly; the observer covers firmware that does not push.

### D-7 Delivery: fork branch → personal CI → TestFlight; upstream only after sign-off

- **Decision**: code lands on `feature/viaim-recdot` in a new fork worktree `omi-recdot/`,
  merged into `personal/ci` for `ios-personal-dogfood` builds (F-7). `Info.plist` gains
  `UISupportedExternalAccessoryProtocols = [com.vision.voyager]` and `external-accessory`. Android
  parity is written after the iOS TestFlight pass and labelled unverified. Upstream issue then PR
  only after the user's validation.
- **Rationale**: the user's constraints (iOS first, never Android hardware, TestFlight is the only
  proof), and the Omi contribution standard's requirement to state what was exercised.

---

## Part 4 — Open risks carried into tasks

| Risk | Detection | Mitigation |
|---|---|---|
| iOS refuses a second EA session while the viaim app holds one | First TestFlight run with the vendor app installed | Instruct the user to force-quit the vendor app; document in quickstart |
| Two on-device recognisers overload the iPhone | Dropped frames or a growing polling buffer on TestFlight | D-2 energy fallback |
| Input stream stalls on iAP2 | Bytes stop while the accessory stays connected | Dedicated-thread run loop, full drain per event, watchdog that reopens the session |
| Firmware expects a different sample-rate mode | `0x500F/0x5010` report | Both G.722 modes supported; mode read from the attribute, never assumed |
| The buds refuse `0x500B` from a non-vendor host | ACK status ≠ 0 | Not expected (bond code 0); if it happens, FlashRecord remains the both-sides path |
