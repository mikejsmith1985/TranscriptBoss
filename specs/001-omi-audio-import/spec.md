# Feature Specification: Audio File Import for Omi

**Feature Branch**: `feature/omi-audio-import`

**Created**: 2026-08-05 · **Rewritten**: 2026-08-06

**Status**: Draft — re-scoped after the file-ingestion spike

**Input**: User description: "I want an application in the Omi App Store that can import audio files from other sources — in my case my earbuds."

---

## Why This Was Rewritten

The first version of this specification assumed a desktop companion that transcribed recordings on the user's PC. Two facts from the user made that architecture wrong:

1. **The recordings live on the phone**, not on a computer. Any design requiring a file transfer to a PC fails at step one.
2. **The need is roughly 20 hours a week.** Omi's free cloud allowance is ~20 hours a *month*, so the cloud path cannot carry this either.

What remains is the thing the user said at the outset: **Omi already does unlimited free transcription on the phone.** The product is not a second transcription engine. It is the missing doorway into the one that is already there.

The [spike](./research.md) confirmed that doorway is short. Omi's audio ingress is already an abstraction — `AudioSource.processBytes()` → frames → transcription socket — and the microphone is merely one producer of bytes. Nothing in that path is tied to hardware.

---

## What This Feature Is

**A change to the Omi mobile application** that lets a person pick an audio file and have Omi transcribe it exactly as though Omi had recorded it — on the device, free, unlimited, and unchanged in every step after transcription.

There is no companion app, no server, no account linking, and no second transcription engine. The audio never leaves the phone.

---

## Platform Reality Check *(verified from source, 2026-08-06)*

| Question | Answer | Consequence |
|---|---|---|
| Does Omi transcribe on-device, free and unlimited? | ✅ Yes | `PurePollingSocket` + `OnDeviceWhisperProvider` (Android) / `OnDeviceAppleProvider` (iOS) |
| Is the audio ingress tied to the microphone? | ❌ No | `AudioSource` is an abstract interface with two existing implementations; bytes may come from anywhere |
| Is the pipeline real-time locked? | ❌ No | `send()` is unpaced and the transcript timeline advances by *audio duration*, not wall clock |
| Does an audio-file import already exist? | ❌ No | The existing "Import Data" is a ZIP uploaded for **cloud** processing (Limitless). This would be the first on-device one |
| Can a conversation be produced from imported audio? | ✅ Yes | Segments accumulate through `_processNewSegmentReceived`; `forceProcessingCurrentConversation()` closes the session into a conversation |
| Does the on-device engine separate speakers? | ❌ No | One anonymous speaker, no word timings. Accepted — see Out of Scope |
| Can the conversation carry the recording's real time? | ⚠️ Unresolved | The session is stamped when it runs. See Open Questions |

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import a recording and get a transcript (Priority: P1) 🎯 MVP

I have an audio file on my phone — exported from my earbuds' app, a voice memo, anything. I open Omi, choose the file, and it becomes a conversation in Omi with a transcript, a title and a summary, exactly like one Omi recorded itself. It costs nothing and there is no limit on how much I do this.

**Why this priority**: This is the entire product. The user stated plainly that ingestion plus a clean transcript is already a win, independent of anything else.

**Independent Test**: Pick a recording in Omi, wait, and confirm a conversation appears containing an accurate transcript — with no network transcription call made and no charge incurred.

**Acceptance Scenarios**:

1. **Given** an audio file on the device, **When** the user selects it for import, **Then** Omi transcribes it using the same on-device engine it uses for live capture, and no audio leaves the phone.
2. **Given** a completed import, **When** the user opens their conversations, **Then** the imported recording appears as a normal conversation with a transcript, title and summary.
3. **Given** a recording longer than the engine's comfortable single pass, **When** it is imported, **Then** it is processed in pieces and reassembled with no words lost or duplicated at the joins.
4. **Given** an import is running, **When** the user leaves the screen, **Then** the import continues and the user is told when it finishes.
5. **Given** a file the device cannot decode, **When** it is selected, **Then** the user is told which format it is and which formats work, before any processing begins.
6. **Given** a recording containing no speech, **When** it is imported, **Then** the user is told that rather than being shown an empty conversation.

---

### User Story 2 - Know what is happening (Priority: P1)

While a recording is being transcribed I can see how far along it is, roughly how long is left, and — if something goes wrong — what went wrong and what to do about it.

**Why this priority**: A twenty-hour week of recordings means imports that run for a long time. An unexplained wait is indistinguishable from a hang, and a user who cannot tell the difference will kill the app and lose the work.

**Independent Test**: Start an import of a long recording and confirm progress advances visibly, an estimate is shown, and interrupting it produces a message that says what to do next.

**Acceptance Scenarios**:

1. **Given** an import in progress, **When** the user watches it, **Then** progress and a remaining-time estimate update as the recording is consumed.
2. **Given** an import that fails, **When** the user is notified, **Then** the message says what happened and what to do, never an error code alone.
3. **Given** an import interrupted by the app closing, **When** the user returns, **Then** they are told it did not finish and can start it again — and no half-finished conversation was created.
4. **Given** the device is low on memory, **When** a long import is running, **Then** the import slows rather than growing until the operating system intervenes.

---

### User Story 3 - Put the conversation at the right time (Priority: P3 — reduced after the T012 spike)

The recording happened yesterday afternoon, not now. I want the conversation to sit at the right point in my Omi timeline so it reads as part of that day.

**Why this priority**: A conversation filed under the wrong day is materially less useful, and every subsequent capability — search, daily summaries, and any future merging — depends on it. It was P2 until the T012 spike established that **the app cannot set a conversation's time at all**.

⚠️ **The full story is not currently deliverable.** Conversations are created by `POST /v1/conversations` with an empty body; the server stamps them, no request field carries a recording time, and none of the seven existing update routes can correct one afterwards. The only place a client-supplied time is honoured is the metered cloud path this feature exists to avoid. Evidence in [research.md](./research.md) Part 4.

**What is delivered instead**: the true recording time is still determined — never substituted with the import time — and is recorded and shown on the conversation, with the limitation stated plainly to the user. The information is preserved so that when the platform can accept it, nothing needs re-deriving.

**Independent Test**: Import a recording made yesterday; the conversation displays yesterday as its recording time, and the user is told it is filed under today.

**Acceptance Scenarios**:

1. **Given** a file carrying its recording date, **When** it is imported, **Then** that date is determined, stored, and shown on the conversation.
2. **Given** a file whose date cannot be determined, **When** it is imported, **Then** the user is asked rather than the import time being used silently.
3. **Given** any import, **When** the conversation is created, **Then** the user is told it is filed at the import time and why.
4. **Given** a recording time the user disagrees with, **When** they correct it, **Then** the stored and displayed recording time changes.

---

### User Story 4 - Bring in a backlog (Priority: P3)

I have weeks of recordings already sitting in my earbuds' app. I want to import them without babysitting each one.

**Why this priority**: Real value at ~20 hours a week, but useless until a single import is reliable.

**Independent Test**: Select several recordings, leave the phone, and return to find all of them imported as separate conversations.

**Acceptance Scenarios**:

1. **Given** several selected recordings, **When** the import starts, **Then** each becomes its own conversation and they are processed one after another.
2. **Given** a queue in progress, **When** one recording fails, **Then** the rest still complete and the failure is reported against that recording alone.
3. **Given** a recording already imported, **When** it is selected again, **Then** the user is told rather than a duplicate conversation being created.
4. **Given** a long queue, **When** the device is not charging or is thermally limited, **Then** the queue pauses rather than draining the battery flat.

---

### User Story 5 - Merge with what Omi already heard (Priority: P4 — deferred)

When Omi captured its own partial record of the same conversation, the imported version should enrich it rather than sit beside it as a duplicate.

**Why this priority**: **Explicitly out of MVP scope at the user's direction.** It is recorded here because the design should not foreclose it, not because it is being built.

**What would make it possible**: Omi's own conversation already has speaker attribution and knows which utterances are the user's. Anchor-matching an imported flat transcript against those identifies the user's side; the remainder is the other party by elimination. The on-device engine's lack of speaker separation is therefore **not** a blocker for merging — a finding that only matters once this story is picked up.

---

### Edge Cases

**Input**
- File is corrupt, truncated, zero-length, or DRM-protected.
- File is in a container the device cannot decode.
- File is enormous — several hours, or larger than free storage allows to decode.
- File contains only silence, music, or noise.
- The user picks a video file.

**During the import**
- The app is backgrounded, or the OS suspends it.
- The phone locks, or the screen turns off.
- The device runs low on memory, storage, or battery.
- The device gets hot and the OS throttles it.
- A live Omi recording is already in progress.
- The user starts a second import while one is running.
- The user force-quits mid-import.

**Result**
- The engine produces nothing at all.
- The engine produces obvious nonsense (wrong language, heavy accent, poor audio).
- The recording is in a language the on-device model does not support.
- The same recording is imported twice.

---

## Requirements *(mandatory)*

### Import

- **FR-001**: A user MUST be able to select an audio file from their device and submit it for import.
- **FR-002**: The app MUST accept the audio formats consumer voice recorders and phones produce, and MUST reject anything else with a message naming the format found and the formats accepted.
- **FR-002a**: Where a format is decodable on one platform but not the other, the app MUST accept it only where it works, and MUST list only what the phone in the user's hand can decode. A file refused for this reason MUST be described as needing conversion rather than as damaged — the recording is fine, and saying otherwise sends the user looking for a fault that does not exist.
- **FR-003**: The app MUST verify a file is decodable before starting an import, so a failure is immediate rather than discovered after a long wait.
- **FR-004**: The app MUST recognise a recording it has already imported and MUST NOT create a second conversation for it.
- **FR-005**: The app MUST support selecting several recordings at once, importing them in turn.

### Transcription

- **FR-006**: Imported audio MUST be transcribed by the same on-device engine Omi uses for live capture, with no audio leaving the device and no per-recording cost. The resulting transcript text travels to Omi exactly as it does for a conversation Omi recorded itself — that is what makes the result an ordinary Omi conversation, and it is unchanged from the platform's existing behaviour.
- **FR-006a**: Because the conversation is created by Omi, an import MUST require connectivity to finish even though transcription itself is local. The app MUST make that distinction visible rather than appearing stalled: transcription proceeding offline with the conversation pending is a normal state, not a failure.
- **FR-007**: The app MUST convert a submitted recording into the sample rate, channel count and encoding the transcription pipeline expects.
- **FR-008**: The app MUST process recordings longer than a single comfortable pass in overlapping pieces, reassembled with no words lost or duplicated at the joins.
- **FR-009**: The app MUST feed audio no faster than the engine and the device can absorb, so that memory does not grow without bound.
- **FR-010**: The app MUST detect an interrupted or partial transcription and MUST NOT present the result as a finished conversation.
- **FR-011**: Where the recording contains no recognisable speech, the app MUST say so rather than creating an empty conversation.

### The resulting conversation

- **FR-012**: A completed import MUST produce a conversation indistinguishable in kind from one Omi recorded itself — transcript, title, summary and action items — passing through Omi's existing processing unchanged.
- **FR-013**: An imported conversation MUST be identifiable as imported, and MUST record which file it came from.
- **FR-014**: The recording's true time MUST be determined — from the file's metadata, then its name, then by asking the user — and MUST be stored and displayed with the conversation. The import time MUST NOT be substituted silently. *(Reduced from "the conversation MUST be dated when the recording was made" after the T012 spike; see FR-014b.)*
- **FR-014b**: Where the conversation cannot be filed at the recording's time, the app MUST say so plainly rather than letting the user believe the timeline is accurate.
- **FR-015**: The user MUST be able to correct an imported recording's stored time.

### Progress and failure

- **FR-016**: The app MUST show import progress and a remaining-time estimate while a recording is being transcribed.
- **FR-017**: The app MUST continue an import when the user navigates away, and MUST notify them on completion.
- **FR-018**: Every failure MUST be reported as what happened and what to do next, never as an error code alone.
- **FR-019**: An interrupted import MUST leave no partial conversation behind, and MUST be restartable.
- **FR-020**: The app MUST let the user cancel an import in progress.

### Living alongside Omi

- **FR-021**: An import MUST NOT interfere with live Omi recording. Where the two contend, live capture takes precedence and the import waits.
- **FR-022**: The app MUST pause a queue of imports when the device is low on battery or thermally limited, resuming when conditions allow.
- **FR-023**: The change MUST NOT alter the behaviour of any existing Omi capture path.

### Key Entities

- **Import Request**: One selected file — its location, content identity, detected format, duration, and the recording time established for it.
- **Import Job**: The work of turning one Import Request into a conversation — its stage, progress, outcome, and the conversation it produced.
- **File Audio Source**: The adapter presenting a decoded recording to Omi's audio pipeline in the shape the pipeline already consumes.

---

## Success Criteria *(mandatory)*

- **SC-001**: A user can import a recording and see the resulting conversation without reading any documentation.
- **SC-002**: Importing costs nothing per recording, and no audio leaves the device — verified by observing that no transcription request is made off-device.
- **SC-003**: A one-hour recording completes an import without user intervention, and the user is told up front roughly how long it will take.
- **SC-004**: An imported conversation's transcript is of the same quality as the same audio captured live by Omi on the same device.
- **SC-005**: Twenty hours of recordings can be imported in a week on a single phone without the app being killed for memory, and without the device becoming unusable.
- **SC-006**: No import produces a duplicate conversation, across 100 imports including induced interruptions and restarts.
- **SC-007**: An interrupted import leaves no partial conversation, in 100% of induced interruptions.
- **SC-008**: ⚠️ **Not met — known gap.** The intent was that every conversation created from a file carrying a recording date is dated to that date rather than the import time. The T012 spike established the app cannot set a conversation's time at all ([research.md](./research.md) Part 4), so this requires an upstream platform change. **What is met in its place**: the recording's true time is determined, stored and displayed for 100% of files that carry one, the import time is never silently substituted, and the discrepancy is stated to the user. This is recorded as unmet rather than reworded into something that passes.
- **SC-009**: Every failure a user can encounter is reported in a sentence they can act on; none surfaces only as a code.
- **SC-010**: The change introduces no regression in Omi's existing capture paths, demonstrated by the app's existing tests continuing to pass.

---

## Assumptions

- Recordings can be exported from the user's recorder app onto the phone's filesystem, where a file picker can reach them. The product does not integrate with any recorder vendor's app or cloud.
- Omi's free plan continues to include unlimited on-device transcription, and Omi's audio ingress keeps the `AudioSource` shape the spike found.
- The user runs a build of Omi containing this change — initially a fork, ideally upstream. See Dependencies.
- On-device transcription quality is what it is: a small model, one anonymous speaker, no word timings. Accepted for this feature.
- **The two platforms do not decode exactly the same formats.** Core Audio has no Ogg or Vorbis decoder, so an iPhone cannot read `.ogg` however valid the file is, while Android can. Every other accepted format works on both. This is a property of the operating systems, not something the feature can fix, so it is handled by FR-002a rather than papered over.
- The phone has enough free storage to hold a decoded copy of the recording being imported.
- Consent and lawfulness of recording are the user's responsibility.

## Dependencies

- **A build of the Omi app containing this change.** The app is MIT-licensed and Omi publishes a third-party integration guide and pays bounties for contributions, so an upstream pull request is plausible — but acceptance is Omi's decision, not ours. Until then the user runs a fork.
- The device's own audio decoders, for turning consumer formats into the pipeline's expected encoding.
- Omi's existing on-device transcription, conversation creation and summarisation, all used unchanged.

## Out of Scope

- Any second transcription engine, on the phone or off it.
- Any companion desktop application, server, or account linking.
- Speaker separation on imported audio. The on-device engine does not do it, and this feature does not add it.
- Merging an import with an existing Omi conversation (User Story 5 — deferred).
- Reading recordings out of a recorder vendor's app or cloud.
- Live capture from third-party hardware. That is a different feature with a different mechanism, and is being investigated separately.
- Video files, and audio extracted from video.

## Open Questions

- ~~**OQ-1 — Setting the conversation's time.**~~ **Resolved 2026-08-06 by the T012 spike: it cannot be done from within the app.** Conversation creation posts an empty body and the server stamps it; no update route can correct it. FR-014 is reduced, FR-014b added, SC-008 recorded as an unmet gap, and User Story 3 dropped to P3. The upstream change that would fix it — accepting `started_at` on creation, or a PATCH route for it — is identified in [research.md](./research.md) Part 4 and belongs with the Phase 8 contribution.

- **OQ-2 — Decoding consumer formats.** Turning an `.m4a` into the pipeline's expected encoding needs a decoder. Omi already ships `flutter_sound` and `just_audio`, but its existing transcoders handle only the codecs its hardware produces. Whether to reach the platform decoders both operating systems already have, or add a dependency, is a design decision for the plan — it affects app size materially.
