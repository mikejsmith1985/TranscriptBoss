# Tasks: viaim RecDot as a Native Omi Device

**Feature**: `002-viaim-recdot-device` · **Branch**: `feature/viaim-recdot-device` (here) · `feature/viaim-recdot` (fork) · **Date**: 2026-09-06

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) · [data-model.md](./data-model.md) · [contracts/](./contracts/) · [quickstart.md](./quickstart.md) · [protocol.md](./protocol.md)

**Paths** are relative to the fork worktree `omi-recdot/app/` unless they start with `scripts/` or `specs/`, which are in TranscriptBoss.

**Tests are mandatory** (Article V Red → Green; Omi DoD item 1). Every test task is written and seen failing before its implementation task.

---

## Delivery boundaries

- **MVP = Phase 3 + Phase 4** (Stories 1 and 2): the RecDot pairs in Omi and a Teams call on the iPhone yields a both-sides, attributed conversation. Phase 4 ends with the first TestFlight evidence.
- **Android is Phase 7 only**, after the iOS TestFlight pass, and every task there is labelled unverified on hardware.
- **Nothing is pushed to any fork remote or opened upstream** until T063.

---

## Phase 1: Setup

- [X] T001 Create the fork worktree: `git -C omi-fork worktree add ../omi-recdot -b feature/viaim-recdot origin/main` (current upstream main, per the contribution standard), and record the pinned commit in `specs/002-viaim-recdot-device/research.md` Part 2
- [X] T002 Install the Flutter SDK (stable) on this Windows machine so `flutter test` and `dart analyze` run locally for the hermetic layer; no Android SDK is needed for that. Record the version in `research.md`. If declined, every test task below runs only in Codemagic
- [X] T003 [P] Add the owned paths from plan.md's source tree to `scripts/check-article-iv.ps1` `$ownedPaths` (the `services/devices/recdot/`, connector, transport, discoverer, bridge, audio source, capture session, `utils/audio/g722_decoder.dart`, and their tests)
- [X] T004 [P] Read the live upstream rules before writing fork code: `omi-recdot/AGENTS.md`, `omi-recdot/app/AGENTS.md`, `CONTRIBUTING.md`, `docs/doc/developer/Contribution.mdx`, `PRODUCT.md`, `docs/product/invariants/`; run `scripts/pr-preflight --suggest` on an empty diff and note any invariant globs that `lib/services/devices/**` or `ios/Runner/Info.plist` match in `research.md`
- [X] T005 [P] Install the bit-exact Python G.722 package for fixture generation: `python -m pip install --target scripts/.tools/pyg722 G722`, and add `scripts/.tools/` to `.gitignore`

---

## Phase 2: Foundational — the pieces every story needs

**Purpose**: hermetic codec and decoder, the device identity, and the byte pipe. No story can be exercised without them.

### Golden vectors (TranscriptBoss side)

- [X] T006 Write `scripts/generate_recdot_vectors.py` that uses `scripts/recdot_wire.py` to emit `omi-recdot/app/test/fixtures/recdot_golden/{framing,ack,tlv,call_audio,flash_chunk,get_record,advertisement,framer_splits}.json` in the format of `contracts/starot-codec.md`; include the real iPhone advert and a 3-frame stream split at every byte boundary (obligation C-2)
- [X] T007 [P] Write `scripts/generate_g722_vectors.py` that encodes silence, a 1 kHz tone, and white noise at 16 kHz and 8 kHz modes with the Python package (samples passed as int16 arrays, not bytes) and emits `omi-recdot/app/test/fixtures/g722_golden/*.json` with hex G.722 in and hex PCM16 out, including a vector split at frame boundaries for obligation G-3
- [X] T008 [P] Add `scripts/test_generate_vectors.py` asserting both generators are deterministic (same output twice) and that every `input_hex`/`expected` pair decodes through `recdot_wire.py`; run `python -m pytest scripts -q`

### STAROT codec (Dart)

- [X] T009 Write `test/unit/recdot_starot_codec_test.dart` loading every `recdot_golden/*.json` and asserting obligations C-1..C-8 of `contracts/starot-codec.md`; it must fail to compile because `starot_codec.dart` does not exist
- [X] T010 Implement `lib/services/devices/recdot/starot_codec.dart`: `StarotFrame`, `encodeFrame`, `StarotFramer.feed`, ack helpers, `TlvAttribute` encode/decode, `splitCallAudio`, `parseFlashChunk`, `encodeGetRecord`, `decodeAdvertisement`. Pure, no I/O, every function under 40 lines, file header states the Article VII gap (plan C-1). Run T009 to green
- [X] T011 [P] Add opcode and attribute constants to `lib/services/devices/recdot/recdot_commands.dart` (`0x5101`, `0x550B`, `0x5500`, `0x5505/0x5504`, `0x5534`, `0x5410`, `0x500B/0x500C/0x5007/0x500F/0x5010/0x5013/0x5015`, `0x5A75/0x5A76/0x5A77`, `0x5A31..0x5A3D`) with typed request builders and response parsers (`BatteryReport`, `VersionReport`, `SerialReport`, `StoredRecordingEntry`), plus `test/unit/recdot_commands_test.dart` covering each parser against hand-built payloads from protocol.md §5–§7

### G.722 decoder (Dart)

- [X] T012 Write `test/unit/g722_decoder_test.dart` loading `g722_golden/*.json` and asserting G-1..G-4; fails for want of the module
- [X] T013 Implement `lib/utils/audio/g722_decoder.dart` as a pure-Dart port of the public-domain `libg722` decoder (both sample-rate modes, 64 kbit/s, `reset()`), plus an 8k→16k upsampler for the 8 kHz mode; header credits Steve Underwood and CMU and records the Article VII gap (plan C-2). Run T012 to green and note the per-frame decode time from the test output

### Device identity

- [X] T014 Write `test/unit/recdot_device_test.dart` in the shape of `test/unit/rayban_meta_device_test.dart`: `DeviceType.viaimRecDot` serialises by name, legacy-int deserialisation unaffected, `DeviceLocator` with `TransportKind.externalAccessory` and `bluetoothClassic` round-trips, `ConversationSource` maps, no firmware warning. Add the entries the exhaustive maps in `test/unit/rayban_meta_source_mapping_test.dart` and `test/unit/bt_device_from_json_test.dart` require; all fail
- [X] T015 Append `viaimRecDot` to `DeviceType` (`lib/backend/schema/bt_device/bt_device.dart:187`), add cases to the seven exhaustive switches (`bt_device.dart:190,626,645`; `services/devices/connectors/device_connection.dart:125`; `services/capture/conversation_source_for_device.dart:20`; `services/capture/capture_controller.dart:1102`; `utils/device.dart:100`), add `_getDeviceInfoFromViaim` at the `getDeviceInfo` dispatch (`bt_device.dart:363`), append `externalAccessory` and `bluetoothClassic` to `TransportKind` (`services/devices/discovery/device_locator.dart`, never reorder), add the backend `source` string in `omi-recdot/backend/models/conversation_enums.py`. Run T014 to green
- [X] T016 [P] Add the RecDot image asset to `assets/images/` and `Assets.images`, and the synthetic ids `viaim-recdot-link` / `viaim-recdot-bytes` to `lib/services/devices/models.dart`

### Link transport (iOS + Dart)

- [X] T017 Declare `RecDotLinkHostAPI`, `RecDotLinkFlutterAPI` and `RecDotAccessory` in `lib/pigeon_interfaces.dart` per `contracts/link-transport.md`; regenerate with the repo's pigeon command (never edit `*.g.dart` / `*.g.swift`)
- [X] T018 Write `test/unit/recdot_link_transport_test.dart` using a fake `RecDotLinkFlutterAPI` feed: bytes arrive in order through `getCharacteristicStream('viaim-recdot-link','viaim-recdot-bytes')`, `writeCharacteristic` forwards to the host API, unknown ids throw, state stream mirrors native state, and a native disconnect closes the stream without coalescing; fails
- [X] T019 Implement `lib/services/bridges/recdot_link_bridge.dart` (process-wide FlutterApi singleton with static per-device controllers, as `rayban_meta_bridge.dart`) and `lib/services/devices/transports/recdot_link_transport.dart` implementing `DeviceTransport`. Run T018 to green
- [X] T020 Implement `ios/Runner/RecDot/RecDotLinkHostApiImpl.swift`: `listAccessories` from `EAAccessoryManager.shared().connectedAccessories` filtered on `com.vision.voyager`, `registerForLocalNotifications` for connect/disconnect → `onAccessoryListChanged`/`onConnectionStateChanged`, `connect` opens `EASession(accessory:forProtocol:)`, `write` to the output stream, and `ios/Runner/RecDot/RecDotStreamReader.swift` reading on a dedicated thread's run loop and draining `hasBytesAvailable` fully per event → `onBytes`. Register in `AppDelegate.swift` beside the Ray-Ban host API
- [X] T021 Add `com.vision.voyager` to `UISupportedExternalAccessoryProtocols` and `external-accessory` to `UIBackgroundModes` in `ios/Runner/Info.plist`; confirm `personal/ci`'s xcconfig generation does not overwrite it

**Checkpoint**: codec, decoder, identity and byte pipe exist and are green locally. Nothing is user-visible yet.

---

## Phase 3: User Story 1 — Pair the RecDot like an Omi device (P1) 🎯 MVP part 1

**Goal**: the RecDot appears in Omi's device list with battery, connects, reconnects unaided, and never disturbs headset audio.

**Independent Test**: quickstart.md Layer 2 rows 1 and 2.

- [X] T022 [US1] Write `test/unit/recdot_connection_test.dart` with a `FakeDeviceTransport` (copy the one in `test/unit/limitless_golden_test.dart:11-57`): connect sends exactly `55 08 51 01 00 00 00 00`, then `55 04 55 0B`, then `55 07 55 00 02 01 07`, then the battery request and `0x5534`/`0x5410`; an ACK status ≠ 0 at any step fails connect with a message naming the step; battery parses per protocol.md §7; `0x5504` pushes update battery; `performGetFeatures` returns none; fails
- [X] T023 [US1] Implement `lib/services/devices/connectors/viaim_recdot_connection.dart` extending `DeviceConnection`: the connect sequence from data-model.md `LinkSession`, one outstanding request per opcode with a 12 s timeout, `performRetrieveBatteryLevel`, battery-push listener, `performGetAudioCodec` → `pcm16`, all photo/accel/storage hooks returning null/false. Register in `DeviceConnectionFactory.create` with the transport chosen by `locator.kind`. Run T022 to green
- [ ] T024 [P] [US1] Write `test/unit/recdot_discoverer_test.dart`: a fake host API listing one accessory with the protocol yields one `BtDevice` of type `viaimRecDot` with locator kind `externalAccessory`; a list change re-emits; fails
- [ ] T025 [US1] Implement `lib/services/devices/discovery/viaim_recdot_discoverer.dart` (`DeviceDiscoverer`, `isSupported` = iOS or Android) and register it in `lib/services/devices.dart:48-52`. Run T024 to green
- [ ] T026 [US1] Wire the UI gates: `pages/home/device.dart`, `pages/onboarding/find_device/found_devices.dart`, `pages/settings/device_settings.dart` (no firmware update, no LED, no mic gain for this type); ensure the buds show per-part battery and "disconnected" rather than a spinner when the accessory list no longer contains them
- [ ] T027 [US1] Auto-reconnect: on `onAccessoryListChanged` or app resume, if the stored preferred device is a `viaimRecDot` and it is present, connect without user action (follow how `DeviceProvider` reconnects BLE devices at `providers/device_provider.dart:588-593`)
- [ ] T028 [US1] Run `app/test.sh`, `dart format --line-length 120`, `dart analyze` (count must not rise), and `scripts/check-article-iv.ps1`; commit on `feature/viaim-recdot` with a CHANGELOG line in the fork's changelog if one exists for the app
- [ ] T029 [US1] Merge `feature/viaim-recdot` into `personal/ci`, trigger Codemagic `ios-personal-dogfood`, install from TestFlight, force-quit the viaim app, and record quickstart rows 1 and 2 with build number in `specs/002-viaim-recdot-device/quickstart.md` (Evidence log section, to be added)

**Checkpoint**: Story 1 proven on the user's iPhone.

---

## Phase 4: User Story 2 — Capture both sides of a call, live (P1) 🎯 MVP part 2

**Goal**: a Teams call on the iPhone becomes an attributed both-sides conversation via the on-device engine; the call is untouched.

**Independent Test**: quickstart.md Layer 2 rows 3, 4, 5, 9, 10.

### Channel sources and the session

- [ ] T030 [US2] Write `test/unit/recdot_channel_source_test.dart` in the shape of `test/unit/audio_source_test.dart`: a `RecDotChannelSource` fed G.722 bytes emits 320-byte PCM16 frames with wrapping sync keys, `flush` pads, a sample-rate-mode change resets the decoder, and two sources never share decoder state; fails
- [ ] T031 [US2] Implement `lib/services/audio_sources/recdot_channel_source.dart` (`AudioSource`; role user/remote; owns one `G722Decoder`). Run T030 to green
- [ ] T032 [US2] Write `test/unit/recdot_capture_session_test.dart` with a fake transport and fake `ISttProvider`s: `0x500B` is sent on start and `0x500C` on stop/pause; `0x5007` payloads split into the two sources; in on-device mode two `PurePollingSocket`s receive the right channels and the second stamps `speakerId 1, isUser false`; segments from both are delivered in start-time order; a link drop records a gap and re-sends `0x500B` on reconnect; a second session cannot start while one exists; fails
- [ ] T033 [US2] Implement `lib/services/capture/recdot_capture_session.dart` per data-model.md `CaptureSession` (states, gaps, mode resolved from `CustomSttConfig`), and add `TranscriptSegment.mergeByTime` beside `updateSegments` in `lib/backend/schema/transcript_segment.dart` (new function, existing one untouched). Run T032 to green
- [ ] T034 [US2] Integrate with `CaptureController`: when the connected device is `viaimRecDot`, capture runs through `RecDotCaptureSession` instead of `_activeSource` (`capture_controller.dart:1032`), feeding `_processNewSegmentReceived` and closing the conversation through the existing `forceProcessingCurrentConversation` path; add the type to `supportsTranscribeLater` only if native batch is not used (it is not: native `BatchAudioWriter` `default` branch drops frames, so keep the RecDot on the Dart path and document why)
- [ ] T035 [US2] Write two per-channel WAL streams through `LocalWalSync` with distinct device suffixes (`…_user`, `…_remote`) so playback/upload never interleaves (research F-6); test in `test/unit/recdot_capture_session_test.dart` that the WAL names differ and channel count stays 1 each

### Call edges

- [ ] T036 [P] [US2] Write tests in `test/unit/recdot_connection_test.dart`: an unsolicited `0x5013` is answered with `0x5015` and raises a `callStarted` event; the platform call observer event raises the same; a call-ended event raises `callEnded`; a user pause suppresses the start; fails
- [ ] T037 [US2] Implement: `0x5013` handling in the connection; a `RecDotCallObserver` on iOS via `CXCallObserver` exposed through the existing phone-calls Pigeon surface or a new method on `RecDotLinkHostAPI` (`onCallStateChanged`); session start/stop wiring in `CaptureController`; pause/resume UI on the capture page for this device type. Run T036 to green
- [ ] T038 [US2] Add the user-facing messages for every failure path in this story (connect step failed, buds refused start, link lost, recogniser overloaded) to `lib/l10n/app_en.arb` in Omi's style, each saying what happened and what to do (FR-023)

### Proof

- [ ] T039 [US2] Run the full gate (T028's commands); commit; merge to `personal/ci`; Codemagic build; TestFlight
- [ ] T040 [US2] Record quickstart rows 3 (at least the first three calls), 4, 5, 9 and 10 with build number; if row 10 shows the polling buffer growing, open the D-2 energy-attribution fallback as a new task before continuing
- [ ] T041 [US2] Complete the ten-call series for SC-002/SC-003/SC-004 over the following week and record it; this is the gate for Phase 8

**Checkpoint**: MVP proven on the user's iPhone with written evidence.

---

## Phase 5: User Story 3 — Sync recordings made without the phone (P2)

**Goal**: FlashRecord clips become conversations at their true time; deletion on the bud only after durable persistence; never during a call.

**Independent Test**: quickstart.md Layer 2 rows 6, 7, 8.

- [ ] T042 [US3] Write `test/unit/recdot_flash_sync_test.dart` covering every transition and all five invariants in `contracts/flash-transfer-states.md` with a fake transport, a fake import job, and an in-memory persisted job store: list end-marker handling, resume offset arithmetic (÷16, 8 kHz halving, two-way doubling, over-length restart), 3 s silence → interrupted, `0x5A3B` reason 2 → interrupted, protected entries skipped, `0x5A38` only from `deletingOnBud`, three delete failures → abandoned, no duplicate job for an imported identity; fails
- [ ] T043 [US3] Implement `lib/services/devices/recdot/recdot_flash_sync.dart` (`TransferJob` state machine, persisted through Omi's existing local store used by the 001 import job), including the master-switch request when the record is on the other bud (`GAIA_COMMAND_STAROT_DEVICE_CHANGE_MASTER` per protocol.md §6.3), and decode-to-scratch per channel through `G722Decoder`. Run T042 to green
- [ ] T044 [US3] Hand-off to the import job: extend the 001 `ImportRequest` creation with a source of "RecDot" carrying identity, `recordedAt`, and two channel files; two-way clips run through `RecDotCaptureSession` with origin `storedRecording` paced by the import pump; single clips run as an ordinary one-channel import. Test in `test/unit/recdot_flash_sync_test.dart` that `imported` is only set by the job's durable-persist callback
- [ ] T045 [US3] Trigger and guards: start the sync on the connection's "connected and idle" event; refuse while any `CaptureSession` exists or a call is active; stop on call start; show waiting count and total length on connect and per-recording progress in the sync page (`pages/conversations/sync_page.dart`, new section for this device type)
- [ ] T046 [US3] Verification and user messages: length tolerance check, mismatch message, protected message, abandoned message, all in `app_en.arb`
- [ ] T047 [US3] Full gate, commit, `personal/ci` merge, Codemagic, TestFlight; record quickstart rows 6, 7, 8 including the 20 induced interruptions and the duplicate count

---

## Phase 6: User Story 4 — Capture an in-person conversation with the buds (P3)

**Goal**: with no call active, Omi captures the room through the buds' far-field microphones.

**Independent Test**: spec Story 4 acceptance scenarios.

- [ ] T048 [US4] Write tests in `test/unit/recdot_capture_session_test.dart`: origin `liveRoom` sends `0x5A75` (TLV attr 1) on start and `0x5A76` on stop; `0x5A77` payloads (`1 + N×57`) are decoded as mSBC and the two mics are mixed to one user channel; an incoming call ends the room session and starts a call session; fails
- [ ] T049 [US4] Implement mSBC decoding: check Article VII first — if no platform or in-tree mSBC decoder exists (research F-4 says none), port the public-domain SBC decoder's mSBC subset to `lib/utils/audio/msbc_decoder.dart` with golden vectors generated by a documented tool in `scripts/generate_msbc_vectors.py`; header records the gap. Run T048 to green
- [ ] T050 [US4] Wire the capture page's "start recording" for this device type to a `liveRoom` session and the yield-to-call behaviour
- [ ] T051 [US4] Gate, commit, build, TestFlight; record the two acceptance scenarios

---

## Phase 7: User Story 5 — Android parity, unverified by us (P3)

**Goal**: complete, consistent Android code covered by the shared Dart tests; never exercised on hardware by us.

**Independent Test**: shared tests pass; Android build compiles in Codemagic; every mention says unverified.

- [ ] T052 [US5] Implement `android/app/src/main/kotlin/com/friend/ios/recdot/RecDotLinkHostApiImpl.kt` (bonded-and-connected headsets whose name contains `viaim`/`iflybuds` or address starts `20:FF`; insecure RFCOMM on the SPP UUID with the two vendor fallbacks; `write`) and `RecDotSocketReader.kt` (1024-byte reads on a dedicated thread → `onBytes`); register in `MainActivity.kt` beside the phone-mic Pigeon APIs
- [ ] T053 [P] [US5] Android call observer for D-6 (telephony/`InCallService`-free: `AudioManager.mode` transitions) feeding `onCallStateChanged`, mirroring the iOS surface
- [ ] T054 [US5] Confirm `discoverer.isSupported` and the locator kind `bluetoothClassic` route to this transport; run the Android build in Codemagic `android-internal-auto` (or a personal Android workflow if one exists) to prove it compiles; record "compiles, not exercised on hardware" in `research.md`
- [ ] T055 [US5] Label every Android file header and the CHANGELOG line "written for parity; not exercised on hardware by the authors"

---

## Phase 8: Polish, documentation and upstream preparation

- [ ] T056 [P] Write `docs/viaim-recdot-device.md` in the fork, in the shape of `docs/rayban-meta-device.md`: architecture, key components table, audio path, the two transcription modes, FlashRecord state machine, honest limitations (Android unverified, App Store MFi allow-listing), and the force-quit-the-vendor-app instruction
- [ ] T057 [P] Extend `test/unit/recdot_capture_session_test.dart` for **cloud mode**: frames prefixed `0x01`/`0x02` and `channels=2` passed through `TranscriptSegmentSocketService.create`; then add the `channels` parameter to `lib/services/sockets/transcription_service.dart:88-97` defaulting to 1 so no existing caller changes (research F-2). Run to green
- [ ] T058 [P] Add the SC-008 regression guard: run Omi's full `app/test.sh` and confirm the analyzer ratchet count is unchanged; record the numbers in `research.md`
- [ ] T059 Update `CHANGELOG.md` (TranscriptBoss) with the feature summary and the TestFlight evidence rows, and the fork's app changelog if present
- [ ] T060 Update `specs/002-viaim-recdot-device/quickstart.md` with an "Evidence log" section holding every recorded row with date and build number
- [ ] T061 Draft the upstream issue in `specs/002-viaim-recdot-device/upstream-issue.md` (problem + evidence, no implementation epic), naming every matched invariant id from T004
- [ ] T062 Run `make preflight` in the fork and `scripts/pr-preflight --pr-body-file specs/002-viaim-recdot-device/pr-body.md`; fix what they flag
- [ ] T063 **Gate**: only after the user confirms the Phase 4 ten-call series and Phase 5 evidence, and explicitly instructs it, push `feature/viaim-recdot` to the fork remote and open the upstream issue, then the PR

---

## Dependencies

```
Phase 1 ─► Phase 2 ─► Phase 3 (US1) ─► Phase 4 (US2) ─► Phase 5 (US3) ─► Phase 6 (US4)
                                                     └─────────────────► Phase 7 (US5, after the Phase 4 TestFlight pass)
Phase 8 after Phases 4–7; T063 after the user's sign-off.
```

- US2 depends on US1 (a connected device). US3 depends on US2's session for two-way clips and on feature 001's import job. US4 depends on US2's session. US5 depends on the transport contract from Phase 2 and waits for the Phase 4 TestFlight pass by decision.

## Parallel opportunities

- Phase 2: T006 / T007 / T008 together; T009+T010 and T012+T013 in parallel with T014+T015; T016 anytime; T020 in parallel with T018+T019 once T017 is generated.
- Phase 3: T024+T025 beside T022+T023; T026 beside T027.
- Phase 4: T036+T037 beside T030–T035.
- Phase 8: T056, T057, T058 together.

## Implementation strategy

1. Phase 2 entirely on the Windows machine with local `flutter test` (T002): three hermetic pieces green before any native code.
2. Phase 3 is the first TestFlight build: a device that pairs and shows battery, nothing more. It de-risks the accessory session and the vendor-app coexistence question early.
3. Phase 4 is the MVP; row 10 of quickstart decides whether D-2's two-recogniser mode holds or the recorded fallback is taken.
4. Phases 5–6 add value on a working base. Phase 7 is written last and labelled. Phase 8 ends with the user's decision to go upstream.
