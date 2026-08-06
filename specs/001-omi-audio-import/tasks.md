# Tasks: Audio File Import for Omi

**Feature**: `001-omi-audio-import` · **Branch**: `feature/omi-audio-import` · **Date**: 2026-08-06

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/audio-source.md](./contracts/audio-source.md)

**Paths** are relative to the forked Omi app at `omi-fork/app/` unless stated otherwise.

---

## MVP boundary

**Phase 4 ends the MVP.** After T036 a recording on the phone becomes an Omi conversation, transcribed on-device for nothing. Phases 5–8 improve a feature that already works.

---

## Phase 1: Setup

- [X] T001 Fork the Omi monorepo into `omi-fork/` (Flutter app at `omi-fork/app/`), pinned to upstream `f12031d`, remote named `upstream`, branch `feature/file-import`; commit and rationale recorded in `research.md`
- [ ] T001a **Install the Flutter toolchain** — Flutter SDK, Android SDK and platform tools, and a JDK. None is present on this machine, which blocks T002, T003, T011 and every test task. See "Toolchain prerequisite" below
- [ ] T002 Run `bash setup.sh android` (or `ios`) in `omi-fork/app/`, build the unmodified fork, and install it on the target device, confirming the toolchain works before any change is made
- [ ] T003 Verify baseline live capture and on-device transcription on the device — on Android this includes downloading the whisper model — so a later transcription failure cannot be blamed on our change
- [X] T004 [P] Scope the Article IV rules to our files only: `omi-fork/app/analysis_options_transcriptboss.yaml`, `scripts/check_function_length.py` (the 40-line rule, which no Dart linter provides), and `scripts/check-article-iv.ps1` to run both. Omi's `analysis_options.yaml` and `analysis_baseline.json` are left untouched — their ratchet stays their gate (plan.md C-4)
- [X] T005 [P] Create `omi-fork/app/test/unit/import/` and `omi-fork/app/integration_test/import/`, with `integration_test/import/fixtures.dart` synthesising the deterministic fixtures and locating the provided ones
- [ ] T006 [P] Supply the real-speech fixtures on the device — a short clip as `.wav`, `.m4a` and `.mp3`, plus a one-hour recording — in the directory named by `fixtures.dart`. **Not committed**: an hour of 16 kHz mono PCM16 is ~115 MB and would be refused in an upstream pull request

### Toolchain prerequisite (T001a)

Nothing beyond T001 can be verified without this. Confirmed absent on this machine: `flutter`, `dart`, `adb`, `java`, and any Flutter SDK in the usual install locations.

| Needed | Why |
|---|---|
| Flutter SDK (stable) | Builds the app; provides `dart analyze` for the C-4 gate |
| Android SDK + platform tools | `adb` to install on the phone and read device logs |
| JDK 17+ | Gradle, for the Android build |
| A physical Android or iOS phone | On-device transcription and thermal behaviour are the things under test; a simulator cannot show either |

iOS additionally requires macOS and Xcode. If only Windows is available, Android is the whole target and the iOS decoder (T010) cannot be built or verified here.

---

## Phase 2: Foundational

**Blocking.** No user story can start until this phase completes.

- [X] T007 [P] Write the failing contract tests for obligations O-1 to O-5 in `omi-fork/app/test/unit/import/audio_source_contract_test.dart`, following the group structure of the existing `test/unit/audio_source_test.dart` so the file source is held to the same bar `PhoneMicSource` already passes — 320-byte frames, `BleAudioCodec.pcm16`, monotonic sync keys wrapping at 255, `flush` padding the tail, `flush` returning empty when drained
- [X] T008 Define the decode bridge as a **Pigeon** contract in `omi-fork/app/lib/audio_decoder_interface.dart`, following the `lib/phone_mic_interface.dart` precedent — chunked 16 kHz mono PCM16 output, cancellation, and a typed failure for an undecodable file. Generate with `dart run pigeon --input lib/audio_decoder_interface.dart`; never edit the generated `.g.dart`
- [X] T008a Wrap the generated bridge in `omi-fork/app/lib/services/audio/native_decoder.dart` so callers depend on our interface rather than on generated code
- [X] T009 Implement the Android decoder in `omi-fork/app/android/app/src/main/kotlin/com/friend/ios/audiodecoder/` using `MediaExtractor` and `MediaCodec`, resampling and downmixing to 16 kHz mono
- [X] T010 [P] Implement the iOS decoder in `omi-fork/app/ios/Runner/AudioDecoder/` using `AVAudioFile` and `AVAudioConverter`, resampling and downmixing to 16 kHz mono. **Requires macOS and Xcode**
- [ ] T011 Prove decode correctness in `omi-fork/app/integration_test/import/decode_test.dart` — decode each fixture format and compare the PCM against a known-good decode of the same audio, on both platforms. **The two decoders are built differently** (a hand-written windowed-sinc resampler on Android, `AVAudioConverter` on iOS), so this must compare each against a reference rather than against each other, and must cover `.ogg` being accepted on Android and refused on iOS (FR-002a)
- [X] T012 **Spike (D-2)** — **answered: no.** The app cannot set a conversation's time. Creation posts an empty body, no PATCH route touches the date, and the one timestamp convention that works belongs to the metered cloud path. Recorded in `research.md` Part 4; `spec.md` (FR-014 reduced, FR-014b added, SC-008 marked unmet, US3 → P3) and `plan.md` D-2 updated accordingly
- [X] T013 [P] Detect a recording's real format from its bytes in `omi-fork/app/lib/services/import/format_detection.dart`, refusing anything undecodable with the format found and the formats accepted (FR-002, FR-003)
- [X] T014 [P] Identify a recording by a hash of its contents in `omi-fork/app/lib/services/import/content_identity.dart` (data-model Invariant 2)
- [X] T015 [P] Manage the decoded-audio scratch file in `omi-fork/app/lib/services/import/scratch_storage.dart`, deleting on every terminal outcome including a crash on the previous run (Invariant 3)
- [X] T016 Define `ImportRequest`, `ImportJob`, its stages and `ImportFailure` in `omi-fork/app/lib/services/import/import_job.dart`, with the stage transitions of data-model.md and no `conversationId` before `completed` (Invariant 1)

---

## Phase 3: User Story 1 — Import a recording and get a transcript (P1)

**Goal**: A recording on the phone becomes an Omi conversation, transcribed on-device.

**Independent test**: Pick a recording in Omi; a conversation appears with an accurate transcript, and no transcription request leaves the device.

- [X] T017 [P] [US1] Write the failing unit tests for `FileImportSource` frame behaviour in `omi-fork/app/test/unit/import/file_import_source_test.dart` — boundary-length inputs, zero-length input, and `flush` emitting the tail exactly once (O-2, O-3)
- [X] T018 [US1] Implement `FileImportSource` in `omi-fork/app/lib/services/audio_sources/file_import_source.dart`, satisfying the same `AudioSource` contract as the existing sources
- [X] T019 [US1] Make T007's contract tests pass for `FileImportSource`, including the byte-level comparison against `PhoneMicSource` frames (O-1)
- [X] T020 [P] [US1] Write the failing pacing tests in `omi-fork/app/test/unit/import/import_pump_test.dart` — audio in flight stays bounded, and feeding is not tied to wall clock (P-1)
- [X] T021 [US1] Add the transcribed-chunk signal to the polling socket in `omi-fork/app/lib/services/sockets/pure_polling.dart` — an observation only, altering no existing behaviour (D-3, FR-023)
- [X] T022 [US1] Implement the paced pump in `omi-fork/app/lib/services/import/import_pump.dart`, feeding decoded audio until the in-flight bound is reached and waiting on T021's signal (C-2, P-1)
- [X] T023 [US1] Accumulate the transcript timeline by audio duration rather than wall clock in the pump, so segment offsets match the recording (P-3)
- [X] T024 [US1] Drive the import session end-to-end in `omi-fork/app/lib/services/import/import_session.dart` — set the active source, open the transcription socket with the on-device configuration, pump, flush, then close the session into a conversation
- [X] T025 [US1] Refuse to start an import while live capture is running, and yield to a live capture that starts during one (FR-021, P-4)
- [X] T026 [US1] Detect a recording that produced no speech and report it rather than creating an empty conversation (FR-011)
- [X] T027 [US1] Detect an interrupted or partial transcription and refuse to present it as a finished conversation (FR-010, Invariant 1)
- [X] T028 [P] [US1] Mark the resulting conversation as imported and record which file it came from (FR-013, O-5)
- [X] T029 [P] [US1] Build the file picker entry point in `omi-fork/app/lib/pages/import/import_picker_page.dart`, refusing an unsupported file before any work starts
- [X] T030 [US1] Recognise a recording already imported and show the user the conversation it produced, rather than creating a second (FR-004, SC-006)
- [ ] T031 [US1] Prove the word-boundary obligation in `omi-fork/app/integration_test/import/boundary_test.dart` — continuous speech across many chunk boundaries compared word-for-word against a single-pass transcription (P-2, FR-008)
- [ ] T032 [US1] Prove no audio leaves the device in `omi-fork/app/integration_test/import/offline_test.dart` — capture a network log across a full import and confirm no request carries audio and no call reaches `/v2/sync-local-files`, and that Omi's metered usage is unchanged (SC-002). **Not an airplane-mode completion test**: the on-device socket is composed with Omi's backend socket, so the conversation legitimately needs connectivity even though transcription does not (research.md Part 5, FR-006a)
- [ ] T033 [US1] Prove transcript quality in `omi-fork/app/integration_test/import/quality_test.dart` — the same audio imported and captured live, compared on the same device (SC-004)
- [ ] T034 [US1] Prove memory is bounded in `omi-fork/app/integration_test/import/memory_test.dart` — peak memory during a one-hour import, shown flat with respect to recording length (SC-005, P-1)
- [ ] T035 [US1] Prove no leak across imports in `omi-fork/app/integration_test/import/sequence_test.dart` — several imports in sequence with memory measured between each (O-4)
- [ ] T036 [US1] Confirm `bash test.sh` passes unchanged, `scripts/analyze_ratchet.sh` reports no rule above baseline, and live capture is unaffected on the device (SC-010, FR-023) — **MVP complete**

---

## Phase 4: User Story 2 — Know what is happening (P1)

**Goal**: Progress, an estimate, and a failure message the user can act on.

**Independent test**: Start a long import — progress advances, an estimate is shown, and interrupting it produces a message that says what to do.

- [X] T037 [P] [US2] Report progress and a remaining-time estimate from the pump, derived from audio consumed against known duration (FR-016)
- [X] T038 [US2] Build the progress screen in `omi-fork/app/lib/pages/import/import_progress_page.dart`
- [X] T039 [US2] Continue an import when the user navigates away, and notify them when it finishes (FR-017)
- [X] T040 [US2] Support cancelling an import in progress, deleting the scratch file and leaving no conversation (FR-020)
- [X] T041 [US2] Move any job found in a non-terminal stage at app start to failed with a restartable message, never resuming into a half-built conversation (FR-019)
- [~] T042 [P] [US2] **Message content done; localisation blocked.** Every failure is written as what happened and what to do in `import_failures.dart`. The move to `context.l10n` is blocked on the toolchain — Omi forbids hand-editing the ARB and `scripts/add-l10n-key.sh` needs Flutter. Folded into T061a. Original: write every failure in the specification's edge-case list as what happened and what to do, in `omi-fork/app/lib/services/import/import_failures.dart` (FR-018) — every string via `context.l10n.keyName`, with keys added to `lib/l10n/app_en.arb` using `scripts/add-l10n-key.sh`, never by hand-editing the ARB
- [X] T043 [US2] Slow the pump under memory pressure rather than letting it grow until the operating system intervenes
- [ ] T044 [US2] Prove each edge case in `omi-fork/app/integration_test/import/failure_test.dart` — corrupt, truncated, zero-length, silent, video, and undecodable files each produce their intended message (SC-009)
- [ ] T045 [US2] Prove interruption leaves nothing behind in `omi-fork/app/integration_test/import/interruption_test.dart` — force-quit mid-import, restart, and confirm no partial conversation exists (SC-007)

---

## Phase 5: User Story 3 — Preserve the recording's true time (P3 — reduced)

⚠️ **T012 answered: the app cannot set a conversation's time.** This phase is now D-2's fallback, not the original goal.

**Goal**: The recording's true time is determined, stored and shown, and the user is told the conversation is filed at the import time instead. SC-008 stays recorded as an unmet gap.

**Reordering**: at P3 this now sits *below* Phase 6's backlog queue. Task IDs are kept stable rather than renumbered; run Phase 6 first.

**Independent test**: Import a recording made yesterday; the conversation shows yesterday as its recording time and states plainly that it is filed under today.

- [X] T046 [P] [US3] Read a creation date from a recording's embedded metadata in `omi-fork/app/lib/services/import/recording_time.dart`
- [X] T047 [P] [US3] Parse a recording time from common recorder filename patterns
- [X] T048 [US3] Apply the fallback order of data-model.md, flagging a filesystem timestamp from the last few hours for confirmation and never substituting the import time (FR-014)
- [ ] T049 [US3] Ask the user for a recording time when none could be determined, before the import starts
- [X] T050 [US3] Store the established recording time with the import and display it on the conversation, stating plainly that the conversation itself is filed at the import time and why (FR-014b)
- [X] T051 [US3] Let the user correct an imported recording's stored time afterwards (FR-015)
- [ ] T052 [US3] Prove the outcome in `omi-fork/app/integration_test/import/recording_time_test.dart` — a fixture carrying a known recording date has that date determined, stored and displayed, and the import time is never substituted. **SC-008 itself stays unmet**; the test asserts the fallback, not the original criterion
- [ ] T052a [US3] Raise the upstream change with Omi alongside the Phase 8 pull request — an optional `started_at` on `POST /v1/conversations`, or a `PATCH /v1/conversations/{id}/started-at` beside the seven routes that already exist. This is what would let SC-008 be met

---

## Phase 6: User Story 4 — Bring in a backlog (P3)

**Goal**: Several recordings import unattended.

**Independent test**: Select several recordings, leave the phone, return to find each imported as its own conversation.

- [X] T053 [P] [US4] Support multi-selection in the picker (FR-005)
- [X] T054 [US4] Implement the sequential queue in `omi-fork/app/lib/services/import/import_queue.dart` — one import at a time, each producing its own conversation
- [X] T055 [US4] Contain a failure to the recording that caused it, leaving the rest of the queue to complete
- [X] T056 [US4] Skip a recording already imported, telling the user rather than creating a duplicate (FR-004)
- [X] T057 [US4] Pause the queue on low battery or thermal throttling and resume when conditions allow (FR-022)
- [X] T058 [P] [US4] Show queue state — what is done, what is running, what is waiting, what failed
- [ ] T059 [US4] Prove the backlog case in `omi-fork/app/integration_test/import/queue_test.dart` — a mixed queue including one failing recording completes the rest and reports the failure against that recording alone

---

## Phase 7: Polish

- [X] T060 [P] Run `scripts/check-article-iv.ps1` clean — the 40-line rule and doc comments on every public member, explaining why rather than what
- [ ] T061 [P] Confirm `scripts/analyze_ratchet.sh` reports no rule above `analysis_baseline.json`, and `dart format --line-length 120` has been applied to every file this feature added
- [ ] T061a **Complete the localisation.** Every user-facing string reaches the interface through `context.l10n`, and `flutter gen-l10n` emits zero "untranslated message(s)" warnings across all locales. Use the repository's `omi-add-missing-language-keys-l10n` skill for real translations rather than leaving English placeholders — Omi treats an untranslated key as unfinished work, not as polish
- [ ] T062 Run the full `quickstart.md` validation and record the evidence for each success criterion (Article X)
- [ ] T063 Confirm SC-001 with someone who has not read this specification — they import a recording without being told how
- [X] T064 Update `CHANGELOG.md` with the feature and with the archiving of the desktop build (Article VI)
- [X] T065 Move `worker/`, `control-plane/` and `web/` to `chore/archive-desktop-worker` and remove them from `main`, recording in `CHANGELOG.md` what was archived and why (D-5)

---

## Phase 8: Upstream contribution

- [ ] T066 Satisfy Omi's Definition of Done (root `AGENTS.md`): a test per behaviour change, `bash test.sh` green locally, the real user-facing path exercised by hand, the verification evidence written into the commit or PR body, no orphaned `TODO`s, and `make preflight` passing before the PR is opened. Verify UI with `agent-flutter` per `app/AGENTS.md` and attach the screenshot evidence
- [ ] T067 Separate the change into reviewable commits — decode channel, audio source, pump, interface — each independently comprehensible
- [ ] T068 Merge current upstream into the fork and resolve any drift, so the pull request applies to Omi's head rather than our pinned commit
- [ ] T069 Open the pull request, describing the capability, the evidence for each obligation in the contract, and the reasoning for the socket signal of T021
- [ ] T070 Build and sign a local release of the fork so the user keeps a working build regardless of the pull request's outcome (Article VIII)

---

## Dependencies

```
Phase 1 (Setup)
   └─▶ Phase 2 (Foundational) ──────────────┐
          │                                  │
          │  T012 spike ─────────────────────┼──▶ Phase 5 (US3)
          ▼                                  │
       Phase 3 (US1) ── MVP ────▶ Phase 4 (US2)
          │                                  │
          └──────────────────────────────────┴──▶ Phase 6 (US4)
                                                       │
                                              Phase 7 ─┴─▶ Phase 8
```

- **Phase 2 blocks everything.** Nothing can be built on a decoder that does not exist.
- **Phase 5 depends on T012's finding**, not on Phase 3 or 4.
- **Phase 6 depends on Phase 4** — a queue without progress reporting is a black box for hours at a time.
- **Phase 8 depends on Phase 7** — an unpolished contribution wastes a reviewer's time and our own.

## Parallel opportunities

| Phase | Can run together |
|---|---|
| 1 | T004, T005, T006 |
| 2 | T007, T013, T014, T015 — and T009/T010 once T008 fixes the channel's shape, since the two platforms do not touch each other |
| 3 | T017 and T020 (both tests, different files); T028 and T029 |
| 4 | T037 and T042 |
| 5 | T046 and T047 |
| 6 | T053 and T058 |
| 7 | T060 and T061 |

## Task counts

| Phase | Tasks | Story |
|---|---|---|
| 1 — Setup | 6 | — |
| 2 — Foundational | 10 | — |
| 3 — Import and transcribe | 20 | US1 |
| 4 — Progress and failure | 9 | US2 |
| 5 — Recording time | 7 | US3 |
| 6 — Backlog | 7 | US4 |
| 7 — Polish | 6 | — |
| 8 — Upstream | 5 | — |
| **Total** | **70** | |
