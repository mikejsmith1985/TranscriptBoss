# Research: Pacing Spike & Ingestion Path Survey

**Feature**: External Audio Import & Transcript Reconciliation for Omi
**Date**: 2026-08-05
**Method**: Direct source analysis of `BasedHardware/omi` @ `main` (MIT). Shallow sparse clone; Flutter app (`app/lib`), backend routers and sync utilities read directly.
**Status**: Complete — the gating assumption is resolved, and two findings change the product's default path.

---

## 1. The Gating Question

> Can audio be delivered to the Omi app faster than the rate at which it was originally recorded, and still be transcribed correctly?

### Verdict: **YES.** The free on-device transcription path is not wall-clock locked.

### Evidence chain

| # | Location | What it proves |
|---|---|---|
| 1 | `app/lib/services/sockets/pure_polling.dart:225-232` | `send()` appends frames to a plain `List`. No pacing, no rate limit, no wall-clock gate on ingress. |
| 2 | `pure_polling.dart:100-105` | A `Timer.periodic(bufferDuration = 3s)` flushes whatever has accumulated — it does not meter intake. |
| 3 | `pure_polling.dart:115-152` | `_flushBuffer()` concatenates **all** buffered frames and hands the whole blob to `transcribe()`. Larger inflow simply produces larger batches. |
| 4 | `pure_polling.dart:155` | `_audioOffsetSeconds = result.segments.last.end` — the transcript timeline advances by **audio duration**, never by elapsed wall time. |
| 5 | `sockets/on_device_whisper_provider.dart:100` | `duration = audioData.lengthInBytes / 32000.0` — duration is derived from byte count, confirming a pure batch contract. |
| 6 | `on_device_whisper_provider.dart:101-104` | The provider logs `'... (${speedFactor}x real-time)'`. Faster-than-real-time operation is an expected, instrumented condition. |

### Bounds and back-pressure

- **Ceiling** is whisper.cpp throughput on the handset (Android) or Apple Speech via `MethodChannel('com.omi.ios/speech')` (iOS) — not wall clock.
- Back-pressure is a single `_isProcessing` guard (`pure_polling.dart:120`); while a batch transcribes, the buffer keeps growing **unbounded in memory**. An injector must therefore pace to roughly measured STT throughput rather than blasting, or it will grow the heap until the OS kills the app.

---

## 2. Finding — the free on-device path produces no speakers and no word timings

This was not anticipated and it matters more than pacing.

| Location | Finding |
|---|---|
| `on_device_whisper_provider.dart:82-84` | `isNoTimestamps: true`, `splitOnWord: false` |
| `on_device_whisper_provider.dart:109` | Every returned segment is hard-coded `speakerId: 0` |
| `on_device_apple_provider.dart:55` | Same — `speakerId: 0`, one flat segment per batch |
| `freemium_transcription_service.dart:63-69, 100-101` | iOS uses Apple Speech; Android requires a downloaded `ggml-*.bin`, preferring **tiny** |

**Consequence:** the free on-phone path yields flat text in ~3-second-plus chunks with cumulative offsets and **a single anonymous speaker**. That is adequate as a matching anchor but cannot produce the speaker-separated two-sided conversation that User Story 3 exists to deliver. Omi's free transcription is real — the user's premise holds — but it is a transcription *floor*, not a diarizing engine.

---

## 3. Finding — a first-class audio-file upload endpoint exists

`POST /v2/sync-local-files` (`app/lib/backend/http/api/conversations.dart:566-622`, `backend/routers/sync.py:849+`).

- Multipart audio upload; returns **202 + `job_id`** (poll `GET /v2/sync-local-files/{job_id}`) or a **200 fast-path** with the finished result.
- Accepts PCM8 / PCM16 / Opus (`backend/utils/sync/files.py:237-289`).
- **The filename carries the capture timestamp.** Convention from `wal.dart:275-281`:
  ```
  audio_{device}_{codec}_{sampleRate}_{channel}_fs{frameSize}_{unixTimestamp}.bin
  ```
  parsed by `parse_sync_filename_timestamp()` (`backend/utils/request_validation.py:98-110`), which accepts seconds or milliseconds. The filename **also** selects the conversation source (`files.py:230-234`).
- This resolves the timestamp problem outright — FR-028 and FR-031 become near-trivial on this path.

### Constraints on it

| Constraint | Detail | Source |
|---|---|---|
| **Metered** | Uses cloud STT; billed as `sync_fresh` / `sync_backfill` | `sync.py:679` |
| **30-day lookback** | `SYNC_BACKFILL_MAX_AGE_SECONDS`, default `30*24*60*60`. Older uploads get a **terminal** 422 `backfill_lookback_exceeded` — retrying can never succeed | `backend/utils/sync/lanes.py:40-41, 103-112` |
| **Future skew** | ±300 s tolerance; beyond it the batch is forced to the backfill lane | `lanes.py:44-45, 93-101` |
| **Admission control** | Backfill slot tokens, one job in flight per account, `backfill_paced` / `backfill_capacity` 429s with `Retry-After` | `sync.py:533-626, 992-1032` |

⚠️ **The 30-day limit directly constrains User Story 7.** "Months of accumulated recordings" cannot be backfilled through this endpoint.

---

## 4. Finding — competitor import and competitor devices are both merged precedent

- `backend/routers/imports.py` — `POST /v1/import/limitless`, plus job status, cancel and delete routes.
- `app/lib/services/devices/connectors/limitless_connection.dart` — a merged BLE connector for a rival wearable, alongside `omi_connection.dart` and `omiglass_connection.dart`.

Importing a competitor's data and connecting a competitor's hardware are both established, already-merged patterns. A Viaim equivalent follows a well-trodden path and is a credible upstream contribution.

---

## 5. Revised Transcription Tiers

The spike changes the ranking. Cost is no longer the only axis that matters — **transcript quality determines whether the reconciliation feature works at all.**

| Tier | Path | Recurring cost | Speed | Speakers | Timestamps |
|---|---|---|---|---|---|
| **A** | User-hosted STT on the desktop component → import API | **Zero** | Fast | ✅ | ✅ word-level |
| **B** | Vendor transcript already exists → import API | **Zero** | Instant | ✅ vendor's | ✅ |
| **C** | Virtual device → Omi's free on-phone STT | **Zero** | Faster than real time | ❌ **none** | ⚠️ coarse |
| **D** | `POST /v2/sync-local-files` | Metered cloud | Fast | ✅ | ✅ via filename |
| **E** | Paid third-party STT → import API | Metered | Fast | ✅ | ✅ |

### Recommendation

**Tier A becomes the default, not Tier C.**

The user's goal is zero recurring transcription cost, and Tier A satisfies it completely — the desktop component already exists in the resolved design (FR-006), and a local engine on that machine costs nothing per recording. Tier A is also the only free path that yields the speaker-separated, word-timestamped transcript that User Story 3 depends on.

Tier C remains valuable and stays in the product as the no-desktop fallback and as the zero-install demonstration path, but it cannot carry the merge feature on its own.

**The project's premise survives intact.** Omi's unlimited free on-phone transcription is real. What the spike changes is which free engine does the work — the user's PC rather than their phone — for the same zero recurring cost, with a materially better transcript.

---

## 6. Open Items for Hardware Validation

Lower priority now that Tier C is a fallback rather than the default, but still unresolved by source analysis:

- **V-1**: Does the official app accept a virtual BLE peripheral advertising the documented Omi service, or is there an undocumented pairing/attestation step?
- **V-2**: Can the import path and the user's real Omi device be connected simultaneously, or does one displace the other?
- **V-3**: Measured whisper.cpp throughput on the target handset, to set the injector's pacing target.
- **V-4**: Behaviour when the phone locks or the app is backgrounded mid-injection.

---

## 7. Technology Decisions (Phase 0)

Each decision names what was chosen, why, and what was rejected. Article VII requires confirming the governing framework does not already provide a capability before building it; the rejections below are that check.

### D-1 — Transcription engine for the default tier: **WhisperX**

- **Decision**: WhisperX — `faster-whisper` (CTranslate2) for transcription, wav2vec2 forced alignment for word-level timings, `pyannote.audio` 3.x for diarization.
- **Rationale**: It is the only free, self-hostable stack that delivers all three things FR-022 and FR-023 require in one pipeline — text, word timings, and speaker labels. Runs on consumer GPU at roughly 10–20× real time and on CPU well below that but unattended. Zero recurring cost, which is the product's founding premise.
- **Alternatives considered**: Plain `whisper.cpp` — no diarization, which is exactly the gap that demoted Tier C. `pyannote` alone — diarization without transcription. Deepgram/AssemblyAI — metered, and belong in Tier E rather than the default. NeMo — heavier operational footprint for no gain here.
- **Consequence**: The worker is Python, because this stack is Python. That decision propagates.

### D-2 — Worker language and shape: **Python 3.12, local FastAPI daemon**

- **Decision**: A long-running local daemon exposing a localhost HTTP API, with the review UI served as static assets against it.
- **Rationale**: Follows D-1. A daemon (rather than a CLI invoked per file) is what FR-012 (monitored locations) and FR-059 (resumable stages) require. An HTTP surface makes the review UI testable with Cypress and real events, satisfying Article V.
- **Alternatives considered**: Tauri or Electron shell with a Python sidecar — two runtimes to ship and debug for a UI that a browser already renders. A pure CLI — cannot host the approval gates FR-055 requires.

### D-3 — Job durability: **SQLite via SQLModel, with an explicit stage machine**

- **Decision**: Stage-by-stage persistence in a local SQLite database; each stage's output is committed before the stage is marked complete.
- **Rationale**: Single-writer, single-process, no server for an end user to operate. The durable store is the queue.
- **Alternatives considered** *(Article VII gate)*: Temporal and Celery are cluster-oriented and would push a broker onto every user's machine. `huey`/`dramatiq` provide task queues but no resumable-stage or compensating-undo semantics, which FR-059 and FR-063 both need. **Documented gap** — recorded at the component.

### D-4 — Summary and action-item derivation: **Claude `claude-opus-5`**

- **Decision**: The `anthropic` Python SDK on `claude-opus-5`, adaptive thinking, structured outputs (`output_config.format`) for the action-item delta so the diff validates against a schema rather than being parsed out of prose.
- **Rationale**: Merged-transcript reconciliation and action-item diffing is exactly the judgment-heavy work the top tier is for, and a schema-constrained delta is what lets the persistence layer refuse an unapproved write (FR-055). Structured outputs remove a whole class of parse failures from a path that touches the user's task list.
- **Alternatives considered**: Local LLM via Ollama — attractive for the zero-cost story, but merge quality is the feature's whole value and this is the one place to spend. Offered as a configurable engine, not the default. Omi's own summarisation — applies to what Omi itself transcribed, not to a transcript we merged.
- **Cost handling**: Default routes through the control plane on the operator's key with disclosure (FR-065); users may supply their own key for direct calls.

### D-5 — Control plane: **FastAPI + PostgreSQL, thin forwarding proxy**

- **Decision**: A hosted service owning the Omi authorisation flow, worker pairing, and a scoped proxy for Omi import/read/task/notification calls.
- **Rationale**: The Omi integration API key is the *developer's* secret, not the user's. Shipping it inside a desktop binary distributed through an app store leaks it to every installer. The proxy exists to keep that credential server-side.
- **Consequence and disclosure**: Finished transcript text transits the control plane on the default path; audio never does. This is required to fulfil the Omi import itself and therefore permitted by FR-068, and it is disclosed under FR-065. Users who opt into the advanced mode (FR-048) with their own credentials bypass the proxy entirely.

### D-6 — Web surface: **React + Vite, one component library, two bundles**

- **Decision**: Shared components; a worker-served bundle for queue, transcript preview, merge diff and approvals, and a control-plane-served bundle for authorisation and pairing. Typed clients generated from the two OpenAPI contracts.
- **Rationale**: The two surfaces show the same objects; building them separately guarantees drift. Generated clients make a contract change a compile error.

### D-7 — Test strategy per Article V

- **Unit**: pytest, fully mocked, asserted under 10 ms.
- **Integration**: testcontainers PostgreSQL, real ffmpeg, real WhisperX against short fixtures — real infrastructure, never mocked drivers.
- **Contract**: Schemathesis against Omi's published OpenAPI plus a Prism mock, so platform drift (R-3) fails a test rather than a user's import.
- **UX**: Cypress with `cypress-real-events`, launched via `run-dev-clean.ps1`, never against a built binary.

### D-8 — Secrets

Omi app integration key, Anthropic API key, and database URL are Forge Vault entries injected at run time (Article IX). Per-user Omi credentials on the worker live in the OS keychain via `keyring`, never in SQLite, so a copied database file carries no credentials.

---

# Part 2 — The Phone-Only Pivot (2026-08-06)

Everything above was researched for a desktop companion. Two facts from the user retired that architecture: **the recordings are on the phone**, and the volume is **~20 hours a week** against a free cloud allowance of ~20 hours a month. What follows is the research for the replacement, and it supersedes Part 1 wherever the two disagree.

## The ingestion spike

Read against the Omi app at commit `f12031d`.

### F-1 — Audio ingress is already an abstraction

`lib/services/audio_sources/audio_source.dart:54` declares `AudioSource` with `processBytes`, `getSocketPayload`, `flush`, `codec`, `deviceId`, `deviceModel`. Two implementations exist: `ble_device_source.dart:11` (`BleDeviceSource`) and `phone_mic_source.dart:12` (`PhoneMicSource`).

Nothing in the interface refers to hardware. A third implementation whose bytes come from a file is a peer of the two that exist, not a special case.

### F-2 — The ingress pattern is one shape, repeated

`lib/services/capture/capture_controller.dart` at lines 223, 912, 1378 and 1428:

```dart
final frames = _activeSource?.processBytes(bytes) ?? [];
for (final frame in frames) {
  _wal.getSyncs().phone.onFrameCaptured(frame);
  if (_socket?.state == SocketServiceState.connected) {
    _socket?.send(frame.payload);
    _wal.getSyncs().phone.markFrameSynced(frame.syncKey);
  }
}
```

A file import drives exactly this loop. Everything downstream is reached without modification.

### F-3 — The pipeline is not wall-clock locked *(the gating question)*

**Verdict: it is not.** `lib/services/sockets/pure_polling.dart`:

- `:225` — `send()` appends to `_audioFrames`. No pacing, no rate limit, no timing check.
- `:100` — a `Timer.periodic` fires every `bufferDuration`.
- `:115-152` — `_flushBuffer()` concatenates everything accumulated and calls `sttProvider.transcribe(audioData, audioOffsetSeconds: _audioOffsetSeconds)`.
- `:155` — `_audioOffsetSeconds = result.segments.last.end`.

The transcript timeline advances by **transcribed audio duration**, not by elapsed time. Audio may therefore be fed faster than real time and the resulting transcript is still correctly positioned.

**But the same code sets the pacing requirement.** `_flushBuffer` transcribes whatever accumulated since the last tick. Feeding a one-hour file at decoder speed would put an hour of audio into one buffer and one `transcribe` call. Hence D-3 in the plan: bound *audio in flight*, not wall clock.

### F-4 — Conversation creation is reachable

`capture_controller.dart`:
- `:326` `startNewOfflineRecording()`
- `:1732-1733` `TranscriptSegment.fromJson` → `_processNewSegmentReceived`
- `:2111` `onSegmentReceived(List<TranscriptSegment>)`
- `:1885` `forceProcessingCurrentConversation()` — drains the write-ahead-log tail via `finalizeCurrentSession()`, resets state, and adds a processing `ServerConversation`

So: set the source, open the socket, pump, flush, force-process. The conversation, title, summary and action items are Omi's existing code.

### F-5 — No on-device audio import exists today

`lib/backend/http/api/imports.dart:105` — `startLimitlessImport(File zipFile, {String language})` posts a multipart ZIP to `v1/import/limitless`. That is **cloud** processing of a competitor's export, not on-device audio import. This feature would be the first of its kind in the app, which also means there is no existing pattern to conform to.

### F-6 — The on-device engine does not separate speakers

`lib/services/sockets/on_device_whisper_provider.dart`:
- `:82-84` — `isNoTimestamps: true, splitOnWord: false`
- `:100` — `duration = audioData.lengthInBytes / 32000.0` (16 kHz, 16-bit, mono)
- `:109` — `speakerId: 0`, hard-coded

One anonymous speaker, no word timings. Accepted for this feature (spec: Out of Scope).

**Why this does not block future merging**: Omi's own conversation already marks which utterances are the user's. Anchor-matching an imported flat transcript against them identifies the user's side; the remainder is the other party by elimination. The imported transcript never needs its own diarization. Recorded here so User Story 5 is not dismissed on a false premise later.

### F-7 — The on-device configuration is selectable in code

`lib/services/sockets/transcription_service.dart:410-445` — `_createPollingSocket(int sampleRate, BleAudioCodec codec, CustomSttConfig config)` builds a `PurePollingSocket` with `OnDeviceAppleProvider` on iOS or `OnDeviceWhisperProvider` on Android when `config.provider == SttProvider.onDeviceWhisper`. `lib/services/freemium_transcription_service.dart` supplies that configuration via `getFreemiumConfig()` and `createOnDeviceSttConfig()`; iOS is always ready, Android requires a downloaded `ggml-*.bin` and prefers `tiny`.

An import can therefore request the free on-device path explicitly rather than hoping to inherit it.

### F-8 — Nothing in the app can decode a consumer audio file

`app/pubspec.yaml` carries `flutter_sound: 9.25.1`, `just_audio: ^0.9.39`, `opus_flutter: ^3.0.3`, `opus_dart`, `audio_session` — and **no ffmpeg**.

`lib/utils/audio/audio_transcoder.dart` exposes `AudioTranscoderFactory.createToWav({sourceCodec, sampleRate, channels})` with `PassThroughTranscoder`, `PcmToWavTranscoder`, `OpusToWavTranscoder`, `RawPcmTranscoder`, `OpusToRawPcmTranscoder` and `OpusFramesToWavTranscoder`. Every one handles PCM or Opus — the codecs Omi's own hardware produces. **None can read an `.m4a` or `.mp3`.**

This is the single genuine gap the feature must fill, and the reason for decision D-1 (native platform decoders via a method channel). See plan.md for why `ffmpeg_kit_flutter` was rejected.

## What Part 1 research survives

| Part 1 item | Status |
|---|---|
| Content-hash identity for duplicate suppression | **Survives** — same problem, same answer (task T014) |
| Recording-time fallback order, never substituting import time | **Survives** — carried into data-model.md |
| User-facing error taxonomy (what happened / what to do) | **Survives** — carried into FR-018 |
| Anchor-matching design for reconciliation | **Survives, unused** — needed only if User Story 5 is picked up |
| Transcription tier table (A–E) | **Retired** — there is one tier now: Omi's on-device engine |
| Local transcription engine, router, worker daemon | **Retired** — see plan.md D-5 |
| Control plane, hosted proxy, account linking | **Retired for this feature** — required only by User Story 5 |

## Open — the hardware alternative

The user asked whether their viaim RecDot earbuds could be made to work with Omi natively, which would remove the import step entirely.

**Unknown, and worth 20 minutes to find out.** Omi's device protocol is documented — device name `Omi`, service `19B10000-E8F2-537E-4F6C-D104768A1214`, audio characteristic `...0001`, codec characteristic `...0002`, PCM16 or Opus at 16 kHz, a 3-byte header of packet number and index followed by 160 samples. Third-party wearables are integrated by adding a `DeviceType` value, subclassing `DeviceConnection`, and registering it in `DeviceConnectionFactory`; `limitless_connection.dart` is the merged precedent, and Omi pays bounties for these.

The unanswered question is whether the RecDot **streams** audio over Bluetooth during recording or stores it and syncs afterwards. Only the first is compatible. No public teardown exists.

**How to find out**: Android Developer Options -> enable Bluetooth HCI snoop log -> record with the Viaim app -> pull `/sdcard/btsnoop_hci.log` -> open in Wireshark. Steady GATT notifications throughout the recording mean it streams. A quiet channel followed by a burst afterwards means it does not.

If it streams, a native `DeviceConnection` is strictly better than importing — live capture, correct timestamps, no decode step, and no file handling at all. If it does not, file import is the only route, which is what this plan builds. **The two are independent; this finding does not gate any task here.**

---

# Part 3 — Phase 1 Setup Record (2026-08-06)

## The pin (T001)

| | |
|---|---|
| Fork root | `omi-fork/` — its own git repository, not tracked by TranscriptBoss |
| Upstream | `https://github.com/BasedHardware/omi.git`, remote named `upstream` |
| Pinned commit | `f12031d15ea177bf8f6ac0781d7f28f3dc433eae` (2026-08-05, "fix(agent-vm): isolate dev control-plane projects (#11150)") |
| Our branch | `feature/file-import` |
| Clone type | `--filter=blob:none`, full history — blobs fetch on demand, and full history is what makes merging upstream possible later |

**Why this commit**: it is the one every file:line reference in Part 2 was read against. Pinning anywhere else would silently invalidate the evidence this plan rests on. Verified after pinning — `audio_source.dart:54`, `pure_polling.dart:225`, `capture_controller.dart:1885` and `on_device_whisper_provider.dart:109` all resolve to exactly what Part 2 records.

**Why a sibling repository rather than a subdirectory of TranscriptBoss**: D-4's goal is a pull request against Omi, which requires real commits on Omi's own history. A copy of their files inside our tree cannot produce one. TranscriptBoss owns the specification; the fork owns the code; the pinned commit above is what binds them.

**Layout note**: Omi is a monorepo. The Flutter app is at `app/` inside it, alongside `backend/`, `desktop/`, `omi/firmware/`, `sdks/` and others. Our fork root is therefore `omi-fork/` and every path in the plan is `omi-fork/app/...`.

## What the host project requires of us

Reading `AGENTS.md` and `app/AGENTS.md` changed four planned tasks. Recorded in plan.md → Host Project Conventions; summarised here because each was a surprise.

1. **Pigeon, not a hand-written method channel.** `lib/phone_mic_interface.dart` is a near-exact precedent — a native audio module streaming PCM frames to Dart. D-1 updated.
2. **An analyzer ratchet already exists** (`scripts/analyze_ratchet.sh` + `analysis_baseline.json`), counting lint occurrences per rule across the whole app. Article VII says do not rebuild it — and it is why our stricter rules had to be scoped to our own files rather than switched on globally (C-4).
3. **Every user-facing string must be localised** across 49 locales, with `flutter gen-l10n` reporting zero untranslated messages. This makes localisation a completion condition for FR-018, not a polish item. New task T061a.
4. **`test/` must be hermetic** because `bash test.sh` runs all of it in CI; device tests live in `integration_test/`, which CI never runs. This matches Article V's split exactly, so our unit tests moved to `test/unit/import/`.

## What the fork already gives us

- **`test/unit/audio_source_test.dart`** tests `BleDeviceSource` and `PhoneMicSource` against the same obligations our contract states. It pins the numbers `FileImportSource` must match: **320-byte frames** (10 ms at 16 kHz 16-bit mono), `BleAudioCodec.pcm16`, sync keys monotonic and wrapping at 255, `flush` zero-padding the tail to a full frame, `flush` returning empty when drained. Contract obligation O-1 is therefore already an upstream test we can be measured against, and T007 extends that file's shape rather than inventing a parallel one.

## Article IV enforcement (T004)

Dart has **no function-length lint**. It lives in `dart_code_metrics`, whose free tier was retired in 2024. That is the documented Article VII gap, filled by `scripts/check_function_length.py` — a brace-depth analyser that blanks comments and string literals before counting, so braces inside them cannot skew the result.

**Verified, not assumed** (Article X). Run against the fork's own code:

| File | Result | Hand-checked |
|---|---|---|
| `audio_source.dart` | pass | — |
| `phone_mic_source.dart` | pass | — |
| `capture_controller.dart` | 10 functions over 40 lines | `streamButton()` reported at line 744, 124 lines — opens 744, closes 867, exactly 124. `_initiateDeviceAudioStreaming()` reported at 1014, 41 lines — opens 1014, closes 1054, exactly 41 |

Both hand-checks matched precisely. The checker lives in TranscriptBoss rather than the fork so the upstream diff carries no check Omi never asked for.

## Blocked — no Flutter toolchain (T001a)

Confirmed absent on this machine: `flutter`, `dart`, `adb`, `java`, and no Flutter SDK in any of the usual install locations (`%LOCALAPPDATA%\flutter`, `C:\flutter`, `C:\src\flutter`, `%USERPROFILE%\flutter`, `C:\tools\flutter`, `%LOCALAPPDATA%\Android\Sdk`).

This blocks T002, T003, T006, T011 and every task that runs a test or an analyzer. It does not block writing code, and it did not block T001, T004 or T005.

Also unresolved: **iOS needs macOS and Xcode.** If the only machine available is Windows, Android is the entire target and T010 cannot be built or verified. That is acceptable for the user's own need — one phone — but it halves the platform coverage an upstream contribution would be expected to carry, and D-4 should be re-read with that in mind.

---

# Part 4 — T012 Spike: Can an Imported Conversation Carry the Recording's Time?

**Date**: 2026-08-06 · **Verdict**: **No, not from within the app.** D-2's fallback branch applies.

## What was checked

### 1. How a conversation is created

`capture_controller.dart:1885 forceProcessingCurrentConversation()` drains the WAL tail, resets state, shows a placeholder, then calls `processInProgressConversation()`.

`lib/backend/http/api/conversations.dart:27`:

```dart
Future<CreateConversationResponse?> processInProgressConversation() async {
  var response = await makeApiCall(
    url: '${Env.apiBaseUrl}v1/conversations',
    headers: {},
    method: 'POST',
    body: jsonEncode({}),          // ← an empty body
  );
```

**The body is empty.** The server finalizes whatever in-progress conversation the streaming session built and stamps it itself. The client supplies nothing that could carry a recording time, and there is no client-side conversation creation to intercept — the on-device path ends at this same call.

Confirmed by search: `started_at` / `startedAt` appears **nowhere** in any request under `lib/backend/http/api/`.

### 2. Whether it can be corrected afterwards

Every `PATCH` under `v1/conversations/{id}`:

| Endpoint | Sets |
|---|---|
| `/title` | title |
| `/segments/text` | a segment's text |
| `/summary` | summary |
| `/segments/assign-bulk` | speaker assignment |
| `/visibility` | shared/private |
| `/starred` | starred |
| `/action-items`, `/action-items/{idx}` | action-item state |

**None sets the conversation's date or time.** There is no route to correct it after creation either.

### 3. The one place a client-supplied time *is* honoured — and why it is no use

`lib/utils/batch_recording.dart` documents the batch filename convention:

```
audio_{device}_{codec}_{sampleRate}_{channel}_fs{frameSize}_{timestamp}.bin
```

with `BatchRecordingInfo.timerStart` described as *"Recording start time, unix seconds"*, parsed from the trailing segment and mirrored by the backend's `/v2/sync-local-files` pipeline.

So writing a batch `.bin` whose filename carries the true recording time **would** produce a correctly dated conversation.

**But `/v2/sync-local-files` is the metered cloud path** — the one Part 2 established has a ~20 hour/month free allowance against a need of ~20 hours/week, and which transcribes in the cloud rather than on the device. Taking it would sacrifice the only reason this feature exists. It is recorded here because it is the obvious-looking shortcut, and the next person to look will find it and need to know why it was refused.

## Consequence

**FR-014 and FR-015 cannot be met on the on-device path.** Per plan.md D-2, the fallback is now the plan:

- The conversation is created at import time, as every conversation is.
- The true recording time is determined (T046–T049 still apply, and still never substitute the import time) and **recorded and displayed on the import**, so the information is not lost.
- The user is told plainly that the conversation sits at the import time and why.
- **SC-008 is explicitly not met** and is carried as a known gap. It is not quietly reinterpreted as met.
- **User Story 3 drops from P2 to P3**, below the backlog queue, because a queue of correctly transcribed conversations is worth more than one conversation at the right time.

## The upstream change this implies

The fix is small and belongs on Omi's side, which makes it a good candidate to raise alongside the Phase 8 pull request rather than to work around:

- **Either** accept an optional `started_at` in the body of `POST /v1/conversations` — the request already posts `{}`, so nothing breaks —
- **or** add a `PATCH /v1/conversations/{id}/started-at` alongside the seven PATCH routes that already exist.

Either would make imported conversations land at the right point in the timeline, and both would also serve the existing batch path more honestly than encoding a timestamp in a filename.

**Note on what is *not* wrong**: segment offsets within the conversation are correct regardless — the transcript's internal timeline advances by audio duration (Part 2, F-3). A one-hour import produces a one-hour conversation. Only its anchor in the day is wrong.

---

# Part 5 — How On-Device Transcription Reaches a Conversation (2026-08-06)

Found while wiring T024. It answers a question Parts 2–4 left implicit and that the whole import session depends on.

## The composite socket

`transcription_service.dart:353-364`:

```dart
final primarySocket = config.isLive
    ? _createStreamingSocket(sampleRate, codec, config)
    : _createPollingSocket(sampleRate, codec, config);

// Wrap with composite service (primary STT + Omi backend)
return _createCompositeService(sampleRate, codec, effectiveLang,
    primarySocket: primarySocket, source: source, sttConfigId: sttConfigId);
```

So the on-device polling socket does **not** replace Omi's backend connection — it is composed with it. The backend WebSocket is `wss://…/v4/listen` carrying `custom_stt=enabled` (`transcription_service.dart:106-128`).

## What this means

| | |
|---|---|
| **Audio** | Never leaves the device. The polling socket transcribes locally via `OnDeviceWhisperProvider` / `OnDeviceAppleProvider` |
| **Text** | Locally-produced segments travel to Omi's backend over the `v4/listen` socket, exactly as they do for every Omi conversation |
| **The conversation** | Built server-side from that session, which is why `processInProgressConversation()` posts an empty body and the server still knows what to finalize (Part 4) |

**This is the architecture working as intended, not a leak.** SC-002 says *audio* does not leave the device, and that holds precisely. The user's requirement was unlimited free transcription without cloud metering, and that is what the on-device engine gives — the text crossing to Omi is the same thing that crosses for a conversation Omi recorded itself, and it is what makes the result an ordinary Omi conversation rather than a note in a separate app.

## Consequence for the import

The import needs no separate route to a conversation. Connect the composite socket with the on-device configuration, feed frames exactly as live capture does, flush, then call `forceProcessingCurrentConversation()`. Everything after the frames is Omi's existing code, unmodified — which is what the plan claimed and this confirms.

It also means the import **must** be online to produce a conversation, even though transcription itself is local. Worth stating plainly: a fully offline import transcribes but has nowhere to put the result. The quickstart's Scenario 2 must therefore test airplane mode as *"transcription still happens with no network transcription call"*, not as *"the whole import completes offline"* — the original wording would have failed for a reason that is not a defect.
