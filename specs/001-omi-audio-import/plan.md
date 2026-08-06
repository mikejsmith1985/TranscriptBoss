# Implementation Plan: Audio File Import for Omi

**Branch**: `feature/omi-audio-import` · **Date**: 2026-08-06 · **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-omi-audio-import/spec.md`

---

## Summary

Add file import to the Omi mobile app so a recording on the phone is transcribed by the on-device engine Omi already runs, producing an ordinary Omi conversation. No audio leaves the device, nothing is metered, and every step after transcription is Omi's existing code, untouched.

The whole feature is one new producer on an interface Omi already has. `AudioSource` abstracts where audio bytes come from; today the two implementations are a Bluetooth device and the phone microphone. This adds a third whose bytes come from a file, plus the loop that drives it and the screen that starts it.

---

## Technical Context

**Language/Version**: Dart 3 / Flutter — the version pinned by the Omi app we fork
**Primary Dependencies**: None added. Native platform decoders reached through a new method channel; everything else is Omi's existing code
**Storage**: The app's existing local stores. A per-import scratch file for decoded audio, deleted when the import ends
**Testing**: `flutter_test` for unit, `integration_test` for on-device behaviour (see Complexity Tracking C-3)
**Target Platform**: Android and iOS — the two platforms Omi's on-device transcription supports
**Project Type**: Mobile — a change to a forked Flutter application
**Performance Goals**: A one-hour recording imports without the app being killed for memory; peak additional memory bounded by one decoded chunk, not by recording length
**Constraints**: Never blocks or degrades live capture; no network transcription call; no per-recording cost
**Scale/Scope**: ~20 hours of audio a week on one phone; single user; no server

---

## Decisions Taken

The specification left two questions open. Both are settled here.

### D-1 — Decoding: native platform decoders, bridged with Pigeon *(resolves OQ-2)*

**Decision**: A native decoder on each platform — `MediaExtractor` + `MediaCodec` on Android, `AVAudioFile`/`AVAudioConverter` on iOS — decoding to 16 kHz mono PCM16 and returning it in chunks, reached from Dart through a **Pigeon** contract rather than a hand-written method channel.

**Why Pigeon**: Omi's `app/AGENTS.md` names Pigeon as the repository's native-bridge mechanism, and `lib/phone_mic_interface.dart` is a near-exact precedent — a native audio capture module streaming PCM frames up to Dart. Following it gives type-safe generated bindings on all three sides and makes the change look native to the codebase, which matters for D-4. A hand-written `MethodChannel` exists in the repo too (phone calls), but it is the older pattern and there is no reason to pick it.

**The frame shape is not ours to choose**: `test/unit/audio_source_test.dart` pins `PhoneMicSource` at 320-byte frames, described there as 10 ms at 16 kHz 16-bit mono, with `BleAudioCodec.pcm16`. The decoder must produce exactly this. Contract obligation O-1 is therefore already expressed as an upstream test we can be measured against.

**Why**: Both operating systems already ship hardware-accelerated decoders for every format a consumer voice recorder produces. Using them costs nothing in app size, needs no maintenance when a codec changes, and matches how Omi already reaches platform capabilities.

**Alternatives rejected**:

| Option | Why not |
|---|---|
| `ffmpeg_kit_flutter` | The project was retired in 2025 and its prebuilt binaries were withdrawn. Adds 9–40 MB to an app whose users already carry it for live capture. Depending on an unmaintained binary for the feature's critical path is not defensible. |
| `flutter_sound` (already present) | Version 9 dropped its ffmpeg dependency. Its remaining conversion helpers do not cover the consumer containers this needs. |
| `just_audio` (already present) | A playback library. It does not expose decoded PCM. |
| WAV only, no decoding | Would satisfy the letter of an MVP and fail the actual user, whose recorder exports `.m4a`. |

**Article VII note**: The framework does not provide this. Flutter has no audio-decoding API; the capability belongs to the platform, and a method channel is Flutter's documented way to reach one.

### D-2 — Recording time: establish feasibility before committing *(resolves OQ-1)*

**Decision**: A spike (T012) settles whether an imported conversation's timestamp can be set from within the app before any of User Story 3 is built.

**✅ Resolved 2026-08-06 — it cannot. The fallback branch is now the plan.**

Evidence in [research.md](./research.md) Part 4: conversation creation is `POST /v1/conversations` with an empty body, so nothing the client sends can carry a time; none of the seven existing PATCH routes touches the date; and the one convention that *does* honour a client-supplied time — the batch filename parsed by `BatchRecordingInfo` — belongs to the metered `/v2/sync-local-files` cloud path this feature exists to avoid.

So: the conversation is created at import time, the true recording time is determined and shown alongside it, the discrepancy is stated to the user, **SC-008 is carried as an unmet gap rather than reworded**, and User Story 3 drops to P3 — below the backlog queue, because a queue of correctly transcribed conversations is worth more than one conversation at the right time.

The upstream fix is small — accept an optional `started_at` on creation, or add a PATCH route for it — and belongs with the Phase 8 contribution rather than being worked around.

**Why a spike rather than a guess**: this was the one requirement not verified against source, and it turned out to be the one that failed. Building Phase 5 on the assumption would have wasted the phase. Every other phase was independent of the answer, so nothing was blocked while it ran — which is exactly why it was scheduled early and off the critical path.

### D-3 — Pacing: backpressure by audio duration, not wall clock

**Decision**: The pump feeds the pipeline until a bounded amount of *audio* is in flight, then waits for transcription to drain before feeding more.

**Why**: The transcription socket buffers whatever it is given and transcribes on a timer. Feeding a one-hour file as fast as the decoder produces it would put an hour of audio into one buffer and one transcription call — the memory failure SC-005 exists to prevent. Pacing by wall clock instead would make a one-hour recording take one hour, which is worse than useless. Bounding *audio in flight* gives correctness and speed at once: the import runs as fast as the device can transcribe, and no faster.

**Consequence**: The socket must signal when a chunk has been transcribed. If no such signal exists, adding one is part of Phase 3 and is the only change this feature makes to existing capture code — a change that adds a notification without altering behaviour (FR-023).

### D-4 — Delivery: a fork now, an upstream pull request as the goal

**Decision**: Develop on a fork of the Omi app pinned to a known upstream commit. Prepare the change to upstream-contribution standard and open a pull request; the user runs the fork build until and unless it is accepted.

**Why**: The user needs this working on their phone, and that cannot wait on someone else's review queue. But a permanent private fork means re-merging every Omi release forever. Building to contribution standard from the start costs little and is the only path that ends with the maintenance burden at zero. Omi is MIT-licensed, publishes an integration guide, and pays bounties for contributions, so acceptance is plausible — but it is their decision, and the plan does not depend on it.

### D-5 — The existing Python build is archived, not deleted

**Decision**: `worker/`, `control-plane/`, `web/` and `omi-app/` move to a branch, `chore/archive-desktop-worker`, and leave the feature branch.

**Corrected 2026-08-06**: this decision originally named the branch `archive/desktop-worker`. Article III permits `feature/*`, `fix/*`, `chore/*` and `docs/*` — there is no `archive/` prefix, and the repository's own pre-commit hook rejects one. The plan was wrong and the constitution was right; the branch is `chore/archive-desktop-worker`.

**Why**: The desktop architecture is wrong for this user — the recordings are on the phone and the volume exceeds any cloud allowance. But roughly two thirds of what was built is about *reconciliation*, not about desktop: the stage machine, the undo journal, the account model and the anchor-matching design all serve User Story 5 if it is ever picked up. Deleting it destroys that; leaving it on `main` implies it is part of the product. A branch is honest about both.

---

## Constitution Check

| Article | Status | How |
|---|---|---|
| I — Prime Directive | ✅ | Native decoders over an abandoned binary; a spike over a guess on the one unverified requirement; upstream-quality contribution over a permanent fork |
| II — Process Protection | ✅ | No process management in this feature. `run-dev-clean.ps1` keeps its PID-only stops |
| III — Branching | ✅ | `feature/omi-audio-import`; every merge to `main` by pull request |
| IV — Code Quality | ✅ | Enforced by `flutter analyze` with the repo's lint set, plus review against the 40-line and doc-comment rules |
| V — Testing | ⚠️ | Three layers preserved; the UX layer uses Flutter's `integration_test` rather than Cypress. See C-3 |
| VI — Documentation | ✅ | `CHANGELOG.md` updated in every behaviour-changing pull request; `specs/001-omi-audio-import/` is the pipeline artifact tree |
| VII — Framework-First | ⚠️ | Three justified builds. See Complexity Tracking |
| VIII — Release | ✅ | Local build and signing; no GitHub Actions |
| IX — Vault Zero-Knowledge | ✅ | The feature handles no secrets at all — nothing leaves the device |
| X — Verification & Proof | ✅ | Every success criterion has a named evidence method in `quickstart.md`. "It transcribed something" is not accepted; SC-002 is proven by observing that no transcription request leaves the device |
| XI — Output Restraint | ✅ | No dashboard; no status documents |
| XII — Response Format | ✅ | Applies to interaction, not artifacts |

---

## Complexity Tracking

Article VII requires that anything built rather than adopted names the gap it fills.

| # | What is built | Gap it fills | Simpler option rejected because |
|---|---|---|---|
| C-1 | A method channel to native audio decoders | Flutter provides no audio decoding API, and the app's existing transcoders handle only the codecs its own hardware produces (PCM and Opus). Nothing in the app can read an `.m4a` | Adding `ffmpeg_kit_flutter` is the obvious alternative and is worse on every axis that matters: retired upstream, binaries withdrawn, tens of megabytes of app size, for a capability both operating systems already have |
| C-2 | A paced pump feeding decoded audio into the pipeline | The existing sources are inherently paced — a microphone and a Bluetooth device produce audio in real time, so nothing in the pipeline needed to limit intake. A file has no such limit | Feeding without pacing is the simpler option and is the direct cause of the memory failure SC-005 forbids. Pacing to real time is equally simple and makes a one-hour import take one hour |
| C-3 | UX verification with `agent-flutter` and `integration_test` rather than Cypress | Article V mandates Cypress with `cypress-real-events`, launched via `run-dev-clean.ps1`. Cypress drives a browser; this feature has no browser, and `run-dev-clean.ps1` launches web bundles this feature does not have | The Article's *intent* is real input events against a real running application rather than synthetic ones, and that intent is met better here than by substituting a browser tool: Omi already mandates `agent-flutter` (Marionette, integrated in debug builds) for verifying every UI change, driving real presses against a real build on a real device, with a screenshot as evidence. Adopting the host project's own real-interaction harness satisfies Article V and Article VII at once |
| C-4 | Article IV enforcement scoped to our files (`analysis_options_transcriptboss.yaml`, `scripts/check-article-iv.ps1`, `scripts/check_function_length.py`) | Omi gates pull requests with an analyzer ratchet counting lint occurrences across the whole app against `analysis_baseline.json`. Our constitution is stricter than Omi's lint set, and Dart has **no** function-length rule at all — that lives in `dart_code_metrics`, whose free tier was retired in 2024 | Turning our rules on project-wide is the simpler option and would either redden Omi's gate or force a baseline rewrite across thousands of lines we did not write — sinking D-4. Omi's standard stays Omi's; ours applies to ours. The function-length checker is the one genuinely new thing, and it exists because nothing off the shelf can do it |

---

## Project Structure

### Documentation

```
specs/001-omi-audio-import/
├── spec.md              # Rewritten for file import
├── plan.md              # This file
├── research.md          # The ingestion spike, with file:line evidence
├── data-model.md        # Import request, import job, file audio source
├── contracts/
│   └── audio-source.md  # The interface the new source must satisfy
├── quickstart.md        # Evidence-based validation for every success criterion
└── tasks.md             # Generated by /speckit-tasks
```

### Source

The deliverable is a change to the Omi Flutter app, developed on a fork.

Omi is a monorepo — its Flutter app lives at `app/` alongside `backend/`, `firmware/`, `sdks/` and others. Our fork root is therefore `omi-fork/` and every path below is inside `omi-fork/app/`.

```
omi-fork/                              # Fork of BasedHardware/omi, pinned commit,
│                                      # remote `upstream`, branch feature/file-import
└── app/                               # ← the Flutter app; all our changes are here
    ├── lib/services/audio_sources/
    │   └── file_import_source.dart    # NEW — the third AudioSource
    ├── lib/services/import/
    │   ├── import_pump.dart           # NEW — paced feed with backpressure (C-2)
    │   ├── import_job.dart            # NEW — one file's progress to a conversation
    │   └── import_queue.dart          # NEW — sequential queue (User Story 4)
    ├── lib/services/audio/
    │   └── native_decoder.dart        # NEW — Dart side of the decode channel (C-1)
    ├── lib/pages/import/              # NEW — picker, progress, failure
    ├── android/.../AudioDecoderPlugin.kt  # NEW — MediaExtractor + MediaCodec
    ├── ios/.../AudioDecoderPlugin.swift   # NEW — AVAudioFile + AVAudioConverter
    ├── test/                          # Unit — mocked, fast (exists upstream)
    └── integration_test/              # On-device, real audio (exists upstream)

specs/                                 # Retained — this repository's purpose
scripts/                               # Retained
CHANGELOG.md                           # Retained

worker/  control-plane/  web/  omi-app/  # Moved to chore/archive-desktop-worker (D-5)
```

**Structure decision**: The product is one change to one application, so there is one source tree — the fork. The previous four-project structure existed to separate a desktop daemon from a hosted control plane and its web bundles; with no desktop daemon and no server, that separation has nothing left to separate.

**Why the fork is a sibling directory and not tracked here**: `omi-fork/` is its own repository with its own history and an `upstream` remote, because D-4's goal is a pull request against Omi — and that requires real commits on Omi's history, not a copy of its files inside ours. TranscriptBoss owns the specification; the fork owns the code. What binds them is the pinned commit recorded in `research.md`, which is what lets anyone reproduce the pairing. `omi-fork/` is in `.gitignore`.

`omi-app/` joins the archive: it held an Omi App Store manifest and listing for an integration app. This feature is a change to the Omi client itself, so there is no App Store app and nothing for those artifacts to describe.

---

## Phases

Numbering matches `tasks.md`.

| Phase | Purpose | Gate to pass |
|---|---|---|
| 1 | Fork the app, pin upstream, prove the untouched build runs on the user's phone | The unmodified fork builds and captures live audio |
| 2 | Native decode bridge (C-1) and the import primitives | An `.m4a` on the device becomes 16 kHz mono PCM16, verified against a known-good decode |
| 3 | `FileImportSource`, the paced pump (C-2, D-3), and end-to-end wiring | **MVP** — a file picked on the phone becomes an Omi conversation, with no network transcription call |
| 4 | Progress, cancellation, failure messages (User Story 2) | Every failure in the edge-case list produces a sentence a user can act on |
| 5 | Recording time (User Story 3) — shaped by the T012 spike (D-2) | Conversations land at the recording's time, or the fallback of D-2 is in place and the spec is updated |
| 6 | The queue (User Story 4) | A backlog imports unattended, pausing on low battery or heat |
| 7 | Polish, localisation completeness, archiving the desktop build | `quickstart.md` passes end to end with evidence recorded |
| 8 | Upstream contribution (D-4) | The change meets Omi's Definition of Done and a pull request is open |

Phase 3 is the MVP boundary. Everything after it improves an already-working feature; nothing after it is required for the user to get transcripts.

---

## Host Project Conventions

The fork is not a blank sheet. Omi's `AGENTS.md` and `app/AGENTS.md` bind this work, and four of their rules change what tasks must do. They are recorded here because discovering them late is what turns a contribution into a rewrite.

| Convention | Where | Consequence for this feature |
|---|---|---|
| **Every user-facing string is localised** — `context.l10n.keyName`, English template plus 48 translations, and `flutter gen-l10n` must report zero untranslated messages | `app/AGENTS.md` → Localization | Every failure message under FR-018 and every label in the import screens needs an ARB key and translations. This is not a polish item; it is a completion condition, and it is why Phase 7 carries a localisation task rather than assuming English is enough |
| **`test/` must be hermetic** — no network, no device, no live backend, because `bash test.sh` runs all of it in CI. Device tests go in `integration_test/`, which CI never runs | `app/AGENTS.md` → Test Patterns | Matches Article V's unit/integration split exactly. Our unit tests go in `test/unit/import/`; everything touching real audio or a real engine goes in `integration_test/import/` |
| **Analyzer ratchet** — `scripts/analyze_ratchet.sh` fails any lint rule rising above `analysis_baseline.json`; errors always fail | `app/AGENTS.md` → Running Tests | We must not raise any count. This is the reason for C-4 |
| **Definition of Done** — behaviour change implies a test change; the component suite passes locally; you exercised the real user-facing path yourself; the verification evidence is written into the commit or PR | root `AGENTS.md` | Aligns with Article X. `quickstart.md` is what produces that evidence, so Phase 7 must complete before Phase 8 rather than alongside it |

Two further facts found in the fork, recorded so they are not rediscovered:

- **`test/unit/audio_source_test.dart` already exists** and tests both `BleDeviceSource` and `PhoneMicSource` against the exact obligations our contract states — buffering to a frame boundary, `flush` padding the tail, `flush` returning empty when there is nothing left. Our tests extend that file's shape rather than inventing a parallel one.
- **Reference audio cannot be committed.** An hour of 16 kHz mono PCM16 is roughly 115 MB, and a pull request carrying it would be refused. Deterministic fixtures (silence, a known-duration tone, a truncated file, an empty file) are synthesised at test time; real speech is read from a named directory on the device, and a test skips with instructions when it is absent.

---

## Risks

| Risk | Consequence | Response |
|---|---|---|
| The on-device engine performs materially worse on recorded-then-imported audio than on live capture | The feature works but the transcripts are not good enough to use | Measured directly in Phase 3 against the same audio captured live (SC-004). If it fails, the cause is almost certainly a sample-rate or gain mismatch in the decode, which is fixable in C-1 |
| Upstream changes `AudioSource` or the transcription socket | The fork stops merging cleanly | The fork is pinned to a known commit; upstream is merged deliberately, not continuously. D-4 is the real mitigation — an accepted contribution ends the problem |
| The recording-time spike (T012) finds no in-app route | User Story 3 slips to a follow-up | Already planned for in D-2; no other phase depends on the answer |
| Long silences compress the transcript timeline | Timestamps after a silent gap read earlier than the audio actually is | **Known, accepted, not ours to fix.** `pure_polling.dart:155` advances the timeline with `_audioOffsetSeconds = result.segments.last.end`, so a chunk yielding no segments — pure silence — does not advance it at all. Live capture rarely hits this because a microphone in a conversation is seldom silent for minutes; an imported recording from a recorder left running easily is. Changing it would alter an existing capture path, which FR-023 forbids, so it is raised with the Phase 8 contribution alongside the `started_at` change rather than patched here. It affects positions *within* a conversation only; total duration and word order are unaffected |
| Omi changes or withdraws free on-device transcription | The feature's premise disappears | Outside our control and outside the product's reach. It is the same risk the user already carries by using Omi at all |
