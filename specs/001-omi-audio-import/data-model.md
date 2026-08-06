# Data Model: Audio File Import for Omi

**Feature**: `001-omi-audio-import` · **Date**: 2026-08-06 · **Plan**: [plan.md](./plan.md)

Three entities, all local to the phone. There is no server, no account model and no synchronisation — everything that made the previous data model large came from an architecture this feature does not have.

---

## Invariants

**Invariant 0 — Nothing here outlives its import.** These entities exist to get one recording through the pipeline. Once a conversation is created, Omi's own conversation record is the durable artifact; the only thing that must survive is enough to recognise a recording already imported (Invariant 2).

**Invariant 1 — A partial transcription is never presented as a conversation.** An import that stops part-way leaves no conversation behind. This is FR-010 and FR-019, and it is the reason `ImportJob` records a stage rather than a boolean.

**Invariant 2 — A recording is identified by its contents, not its name or path.** Filenames change when a file is copied, shared or re-exported; the bytes do not. This is what makes re-selecting a recording a no-op rather than a duplicate conversation (FR-004, SC-006).

**Invariant 3 — Decoded audio is scratch.** The decoded PCM for an import is a temporary file, deleted when the import ends however it ends. An hour of 16 kHz mono PCM16 is about 115 MB; leaving those behind would fill a phone within a week at the user's volume.

---

## ImportRequest

One file the user chose, and what we determined about it before doing any work.

| Field | Type | Notes |
|---|---|---|
| `id` | identifier | |
| `sourceUri` | string | Where the picker returned it from. May become invalid — a content URI can expire — so it is never the identity |
| `displayName` | string | What to call it in the interface |
| `contentHash` | string | Hash of the file's bytes. **The identity** (Invariant 2) |
| `sizeBytes` | integer | |
| `detectedFormat` | string | From the bytes, not the extension. A `.wav` from a messaging app is often a renamed `.m4a`, and transcribing the wrong container yields gibberish rather than an error |
| `durationSeconds` | double | Drives the time estimate (FR-016) and the pump's progress |
| `sampleRate` | integer? | As found; the decoder resamples to what the pipeline wants |
| `channelCount` | integer? | As found; downmixed to mono |
| `recordingTime` | timestamp? | When the recording was made — see `RecordingTimeSource` |
| `recordingTimeSource` | enum | How it was determined |
| `needsTimeConfirmation` | bool | True when the source is weak enough to ask (FR-014) |

**Validation**
- `detectedFormat` must be one the decoder handles; anything else is refused before work starts, naming the format found and the ones accepted (FR-002, FR-003).
- `durationSeconds` must be greater than zero. A zero-length recording is a failure, not an empty conversation.
- `recordingTime` is never silently set to the import time (FR-014).

### RecordingTimeSource

Ordered strongest to weakest. The first that yields a plausible answer wins.

| Value | Meaning | Confirm? |
|---|---|---|
| `embeddedMetadata` | A creation date inside the file itself | No |
| `filename` | Parsed from a name like `REC_20260805_143022` | No |
| `fileSystem` | The file's own modification time | **Yes, when recent** — a timestamp from the last few hours is almost always the moment a messaging app copied the file, not the moment it was recorded |
| `userProvided` | The user said | No |
| `unknown` | Nothing worked | **Yes** — ask; never substitute the import time |

---

## ImportJob

The work of turning one `ImportRequest` into a conversation.

| Field | Type | Notes |
|---|---|---|
| `id` | identifier | |
| `requestId` | reference | The `ImportRequest` |
| `stage` | enum | Where it has got to |
| `secondsDecoded` | double | Feeds progress and the remaining-time estimate |
| `secondsTranscribed` | double | Trails `secondsDecoded` by the in-flight bound (D-3) |
| `startedAt` | timestamp | |
| `endedAt` | timestamp? | |
| `conversationId` | string? | Set **only** once the conversation exists (Invariant 1) |
| `failure` | `ImportFailure`? | |
| `scratchPath` | string? | The decoded audio. Deleted on any terminal stage (Invariant 3) |

### Stages

```
  queued ──▶ decoding ──▶ transcribing ──▶ creatingConversation ──▶ completed
     │           │              │                    │
     │           ▼              ▼                    ▼
     └────────▶ failed ◀────────┴────────────────────┘
     │
     └────────▶ cancelled
```

- `completed` is the **only** stage carrying a `conversationId`.
- `failed` and `cancelled` are terminal and both delete the scratch file.
- A job found in a non-terminal stage at app start was interrupted. It is moved to `failed` with a message saying it did not finish and can be started again (FR-019) — never resumed into a half-built conversation.

**Why no resume**: The previous architecture resumed jobs mid-stage because a desktop transcription pass was expensive and long. Here the expensive work is Omi's own transcription of audio that is still sitting on the phone; starting again is straightforward and cannot produce a half-written conversation. Correctness over cleverness (Article I).

### ImportFailure

| Field | Type | Notes |
|---|---|---|
| `whatHappened` | string | In the user's terms |
| `whatToDo` | string | An action they can actually take |
| `code` | string | For logs and bug reports — **never** shown alone (FR-018) |
| `isRetryable` | bool | A damaged file is not; a low-memory abort is |

---

## FileAudioSource

Not stored — this is the runtime adapter, listed because it is the entity the whole feature turns on. It satisfies the same contract as the microphone and Bluetooth sources, so everything downstream cannot tell the difference.

| Property | Notes |
|---|---|
| `codec` | The encoding the pipeline expects, after decoding |
| `deviceId` | Identifies this import, so frames are attributable |
| `deviceModel` | Marks the conversation as imported (FR-013) |

See [contracts/audio-source.md](./contracts/audio-source.md) for the obligations it must meet.

---

## Import identity and duplicate suppression

The only thing that must persist beyond an import is the set of `contentHash` values already turned into conversations, each with the conversation it produced. Re-selecting a recording finds its hash, and the user is told it is already imported and shown where — rather than a second conversation appearing (FR-004, SC-006).

This survives a reinstall poorly, and that is acceptable: the failure mode is one duplicate conversation after a reinstall, which the user can delete.
